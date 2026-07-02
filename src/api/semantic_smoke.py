#!/usr/bin/env python3
"""Live semantic-search endpoint smoke check (ig#1148).

Exercises the deployed ``GET /api/v1/search/semantic`` endpoint over HTTP and
asserts it is *functional*, not merely reachable:

* **HTTP 200** — a graceful ``503`` means embeddings are **not provisioned** on
  this environment (the exact prod gap behind ig#1148: pgvector extension +
  backfill absent — see ``src/api/routes/search.py`` ``search_semantic``), so it
  fails the smoke rather than passing on a "reachable" endpoint.
* a **non-empty** result set with a strictly positive top similarity, and
* at least one **topically relevant** hit among the top results.

The topical-relevance assertion is what catches the *silent* failure mode this
issue guards against: an environment whose corpus was embedded with a different
embedder than the API queries with. The lean, torch-free API image defaults to
the lexical :class:`~src.enrich.embeddings.HashingEmbedder`
(``EMBEDDING_MODEL=hashing``, ``src/config.py``), while the one-shot re-embed job
uses a multilingual sentence-transformer (``paraphrase-multilingual-MiniLM-L12-v2``).
Both are ``vector(384)``, so a query vector from one and corpus vectors from the
other cosine-compare with **no error** — HTTP 200 with results, but the ranking is
meaningless. A plain "200 + non-empty" probe would wrongly pass; requiring a known
topical keyword in the top hits (the same vocabulary ``verify_recall`` uses) turns
that mismatch into a detectable failure.

This is the endpoint-level counterpart of ``isnad verify-recall`` (which checks
the ``isnad_graph.hadith_embeddings`` table directly, inside the embed container):
the smoke here proves the *deployed API* returns relevant results, which the
DB-side gate — running with its own in-container embedder — cannot.

Usage::

    python scripts/semantic_smoke.py https://isnad.noorinalabs.com
    SEMANTIC_SMOKE_BASE_URL=https://isnad.noorinalabs.com python scripts/semantic_smoke.py
    python scripts/semantic_smoke.py https://isnad.noorinalabs.com --query patience --query prayer
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from src.enrich.embeddings import _RECALL_KEYWORDS, DEFAULT_RECALL_QUERIES

# An HTTP fetcher maps ``(url, timeout_seconds)`` to ``(status_code, json_body)``.
# Injectable so the probe logic is unit-testable without real network I/O.
Fetcher = Callable[[str, float], "tuple[int, dict[str, Any]]"]

SEMANTIC_PATH = "/api/v1/search/semantic"
DEFAULT_TOP_K = 5
DEFAULT_TIMEOUT_S = 15.0


@dataclass
class ProbeResult:
    """Outcome of a single ``/search/semantic`` probe."""

    query: str
    passed: bool
    status_code: int | None
    hits: int
    top_score: float
    keyword_matched: bool
    detail: str


def topical_keywords(query: str) -> tuple[str, ...]:
    """Keywords that count as evidence ``query`` surfaced relevant hadiths.

    Mirrors ``verify_recall``'s vocabulary (``_RECALL_KEYWORDS``) so the HTTP smoke
    and the DB-side recall gate judge relevance identically; an unmapped query
    falls back to matching its own lowercased token.
    """
    return _RECALL_KEYWORDS.get(query.lower(), (query.lower(),))


def evaluate_probe(
    query: str,
    status_code: int,
    payload: dict[str, Any],
    *,
    top_k: int = DEFAULT_TOP_K,
) -> ProbeResult:
    """Judge a single endpoint response — pure, no I/O (the unit-testable core).

    A response passes only when it is HTTP 200 with a non-empty, positively-scored,
    topically-relevant top result. A graceful 503 (embeddings not provisioned) and
    a 200-but-off-topic response (embedder/corpus mismatch) both fail, with a
    distinguishing ``detail``.
    """
    if status_code != 200:
        env_detail = payload.get("detail") if isinstance(payload, dict) else None
        note = f" ({env_detail})" if env_detail else ""
        return ProbeResult(
            query=query,
            passed=False,
            status_code=status_code,
            hits=0,
            top_score=0.0,
            keyword_matched=False,
            detail=f"HTTP {status_code} — semantic search not provisioned here{note}",
        )

    results = payload.get("results") or []
    if not results:
        return ProbeResult(
            query=query,
            passed=False,
            status_code=status_code,
            hits=0,
            top_score=0.0,
            keyword_matched=False,
            detail="HTTP 200 but empty result set — corpus embeddings not backfilled",
        )

    top_results = results[:top_k]
    top_score = float(top_results[0].get("score") or 0.0)
    haystack = " ".join(
        f"{row.get('title') or ''} {row.get('title_ar') or ''}" for row in top_results
    ).lower()
    keywords = topical_keywords(query)
    keyword_matched = any(keyword in haystack for keyword in keywords)
    passed = top_score > 0.0 and keyword_matched

    if passed:
        detail = f"HTTP 200, {len(results)} hits, top_score={top_score:.3f}, keyword match"
    elif top_score <= 0.0:
        detail = "HTTP 200 with results but non-positive top similarity (degenerate embeddings)"
    else:
        detail = (
            "HTTP 200 with results but none topically relevant — likely the query "
            "embedder does not match the corpus embedder (embedder/corpus mismatch)"
        )
    return ProbeResult(
        query=query,
        passed=passed,
        status_code=status_code,
        hits=len(results),
        top_score=top_score,
        keyword_matched=keyword_matched,
        detail=detail,
    )


def _parse_json(body: str) -> dict[str, Any]:
    """Best-effort JSON-object parse; a non-object / unparseable body yields ``{}``."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _urllib_fetch(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
    """Default HTTP GET via the stdlib (no extra runtime dependency).

    A non-2xx response raises ``HTTPError``, which is itself readable — so the
    graceful ``503`` body (its ``detail``) is captured, not discarded.
    """
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), _parse_json(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return int(exc.code), _parse_json(exc.read().decode("utf-8", errors="replace"))


def probe(
    base_url: str,
    query: str,
    *,
    fetcher: Fetcher | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    top_k: int = DEFAULT_TOP_K,
) -> ProbeResult:
    """Fetch and evaluate one ``/search/semantic`` query against ``base_url``.

    ``fetcher`` defaults to the stdlib HTTP fetch, resolved at call time (not bound
    as a default argument) so tests can substitute it via ``monkeypatch``.
    """
    fetch = fetcher or _urllib_fetch
    url = f"{base_url.rstrip('/')}{SEMANTIC_PATH}?q={quote(query)}&limit={top_k}"
    try:
        status_code, payload = fetch(url, timeout)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return ProbeResult(
            query=query,
            passed=False,
            status_code=None,
            hits=0,
            top_score=0.0,
            keyword_matched=False,
            detail=f"request failed: {exc}",
        )
    return evaluate_probe(query, status_code, payload, top_k=top_k)


def run_smoke(
    base_url: str,
    queries: Sequence[str] = DEFAULT_RECALL_QUERIES,
    *,
    fetcher: Fetcher | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    top_k: int = DEFAULT_TOP_K,
) -> list[ProbeResult]:
    """Probe every query and return the per-query results."""
    return [
        probe(base_url, query, fetcher=fetcher, timeout=timeout, top_k=top_k) for query in queries
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: exit non-zero if any semantic probe fails."""
    parser = argparse.ArgumentParser(
        description="Semantic-search endpoint smoke check (ig#1148).",
    )
    parser.add_argument(
        "base_url",
        nargs="?",
        default=os.environ.get("SEMANTIC_SMOKE_BASE_URL", ""),
        help="Base URL of the deployed API (or set SEMANTIC_SMOKE_BASE_URL).",
    )
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Topical query to probe (repeatable). Defaults to the verify-recall set.",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    args = parser.parse_args(argv)

    base_url = str(args.base_url)
    if not base_url:
        parser.error("base_url is required (positional argument or SEMANTIC_SMOKE_BASE_URL)")

    queries: Sequence[str] = tuple(args.queries) if args.queries else DEFAULT_RECALL_QUERIES
    results = run_smoke(base_url, queries, timeout=args.timeout, top_k=args.top_k)

    print(f"Semantic-search smoke — {base_url}{SEMANTIC_PATH}")
    for result in results:
        mark = "PASS" if result.passed else "FAIL"
        print(f"  [{mark}] q={result.query!r}: {result.detail}")

    failures = [result for result in results if not result.passed]
    if failures:
        print(f"RESULT: {len(failures)}/{len(results)} semantic probe(s) failed")
        return 1
    print(f"RESULT: all {len(results)} semantic probe(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
