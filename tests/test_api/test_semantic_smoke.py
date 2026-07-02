"""Unit tests for the semantic-search endpoint smoke check (ig#1148).

The smoke's value over a plain "endpoint reachable" check is that it fails on the
two prod failure modes behind ig#1148 — (1) embeddings not provisioned (graceful
503) and (2) a 200-but-off-topic response from an embedder/corpus mismatch — so
those are the cases pinned here alongside the happy path.
"""

from __future__ import annotations

from typing import Any

from src.api import semantic_smoke
from src.api.semantic_smoke import (
    ProbeResult,
    evaluate_probe,
    main,
    probe,
    run_smoke,
    topical_keywords,
)


def _hit(title: str, score: float = 0.9, title_ar: str = "") -> dict[str, Any]:
    return {"id": "had-1", "type": "hadith", "title": title, "title_ar": title_ar, "score": score}


def test_topical_keywords_mirror_recall_vocabulary() -> None:
    # A mapped query expands to its synonym set; an unmapped one falls back to itself.
    assert "salah" in topical_keywords("prayer")
    assert topical_keywords("zzznotathing") == ("zzznotathing",)


def test_evaluate_pass_on_relevant_200() -> None:
    payload = {"results": [_hit("The reward of patience in adversity", 0.71)], "total": 12}
    result = evaluate_probe("patience", 200, payload)
    assert result.passed is True
    assert result.keyword_matched is True
    assert result.top_score == 0.71
    assert result.hits == 1


def test_evaluate_fails_on_graceful_503() -> None:
    # The exact prod gap: embeddings not provisioned yields the typed 503.
    payload = {"detail": "Semantic search is not yet available on this environment."}
    result = evaluate_probe("prayer", 503, payload)
    assert result.passed is False
    assert result.status_code == 503
    assert "not provisioned" in result.detail
    assert "not yet available" in result.detail


def test_evaluate_fails_on_empty_200() -> None:
    result = evaluate_probe("prayer", 200, {"results": [], "total": 0})
    assert result.passed is False
    assert "empty result set" in result.detail


def test_evaluate_fails_on_offtopic_200_embedder_mismatch() -> None:
    # 200 with results but nothing topical — the silent embedder/corpus mismatch a
    # plain "200 + non-empty" probe would wrongly pass.
    payload = {"results": [_hit("A narration about trade caravans", 0.88)], "total": 30}
    result = evaluate_probe("prayer", 200, payload)
    assert result.passed is False
    assert result.keyword_matched is False
    assert "mismatch" in result.detail


def test_evaluate_fails_on_nonpositive_score() -> None:
    payload = {"results": [_hit("prayer congregation", 0.0)], "total": 1}
    result = evaluate_probe("prayer", 200, payload)
    assert result.passed is False
    assert "non-positive" in result.detail


def test_probe_uses_injected_fetcher_and_builds_url() -> None:
    seen: dict[str, Any] = {}

    def fake_fetch(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        seen["url"] = url
        return 200, {"results": [_hit("patience and perseverance")], "total": 3}

    result = probe("https://isnad.example.com/", "patience", fetcher=fake_fetch)
    assert result.passed is True
    assert seen["url"] == "https://isnad.example.com/api/v1/search/semantic?q=patience&limit=5"


def test_probe_handles_transport_error() -> None:
    import urllib.error

    def boom(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        raise urllib.error.URLError("connection refused")

    result = probe("https://isnad.example.com", "prayer", fetcher=boom)
    assert result.passed is False
    assert result.status_code is None
    assert "request failed" in result.detail


def test_run_smoke_aggregates_per_query() -> None:
    def fake_fetch(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {"results": [_hit("patience prayer salah")], "total": 5}

    results = run_smoke("https://isnad.example.com", ("patience", "prayer"), fetcher=fake_fetch)
    assert [r.query for r in results] == ["patience", "prayer"]
    assert all(isinstance(r, ProbeResult) and r.passed for r in results)


def test_main_returns_zero_on_all_pass(monkeypatch: Any, capsys: Any) -> None:
    def fake_fetch(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 200, {"results": [_hit("patience prayer salah")], "total": 5}

    monkeypatch.setattr(semantic_smoke, "_urllib_fetch", fake_fetch)
    rc = main(["https://isnad.example.com", "--query", "patience"])
    assert rc == 0
    assert "all 1 semantic probe(s) passed" in capsys.readouterr().out


def test_main_returns_one_on_failure(monkeypatch: Any, capsys: Any) -> None:
    def fake_fetch(url: str, timeout: float) -> tuple[int, dict[str, Any]]:
        return 503, {"detail": "Semantic search is not yet available on this environment."}

    monkeypatch.setattr(semantic_smoke, "_urllib_fetch", fake_fetch)
    rc = main(["https://isnad.example.com", "--query", "prayer"])
    assert rc == 1
    assert "failed" in capsys.readouterr().out
