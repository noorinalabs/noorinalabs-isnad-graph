"""Search endpoints: full-text and semantic."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.api.deps import get_neo4j, get_pg
from src.api.models import SearchResult, SearchResultsResponse
from src.config import get_settings
from src.enrich.embeddings import get_embedder, to_pgvector_literal
from src.utils.grades import normalize_grade
from src.utils.neo4j_client import Neo4jClient
from src.utils.pg_client import PgClient
from src.utils.topics import canonical_topics_for_tags

router = APIRouter()

log = logging.getLogger(__name__)


def _death_year_to_century(death_year_ah: object) -> int | None:
    """Map a Hijri death year to its 1-based century (124 AH -> 2nd century).

    Returns ``None`` for missing/non-positive years so the century facet treats
    the narrator as unknown rather than excluding them. (#1036)
    """
    if isinstance(death_year_ah, int) and death_year_ah > 0:
        return (death_year_ah - 1) // 100 + 1
    return None


def saturate_relevance(score: float, k: float) -> float:
    """Map a raw BM25-style score onto a badge-friendly [0, 1) confidence.

    Uses the saturating transform ``score / (score + k)``: strictly monotonic in
    ``score`` (preserves relative ranking), bounded to ``[0, 1)`` for any
    non-negative input, and — unlike the within-result-set max-normalisation it
    replaces (ig#1065) — it does NOT force the top hit of every query to exactly
    1.0. A weak top hit therefore reads as a weak *absolute* confidence rather
    than 100%, which is the whole point of ig#1070.

    ``k`` is the half-saturation constant (the raw score that maps to 0.5); it is
    configurable via ``Settings.search.relevance_saturation_k`` and must be
    calibrated against the real score distribution — see ``SearchSettings``.
    Negative raw scores are clamped to 0.0 (degenerate / never expected for
    full-text BM25, but cheap insurance).
    """
    if score <= 0.0:
        return 0.0
    return score / (score + k)


@router.get("/search", response_model=SearchResultsResponse)
def search(
    q: str = Query("", max_length=500, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> SearchResultsResponse:
    """Full-text search across hadiths and narrators.

    Uses Neo4j full-text indexes (``narrator_search``, ``hadith_search``)
    when available, falling back to ``CONTAINS`` substring matching.

    An empty or blank ``q`` is a clean no-op: it returns ``200`` with an empty
    result set rather than ``422``, so the frontend firing a search on an empty
    box (or on initial load) lands on a valid "no results yet" state instead of
    an API error.
    """
    # Short-circuit blank queries before touching Neo4j — nothing to match, and
    # a full-text query on empty input is meaningless.
    if not q.strip():
        return SearchResultsResponse(results=[], total=0, query=q)

    results: list[SearchResult] = []

    # --- Narrator search via full-text index ---
    narrator_rows = _fulltext_narrator_search(neo4j, q, limit)
    for r in narrator_rows:
        results.append(
            SearchResult(
                id=r["id"],
                type="narrator",
                title=r.get("name_en") or r["name_ar"],
                title_ar=r["name_ar"],
                score=r["score"],
                century=_death_year_to_century(r.get("death_year_ah")),
            )
        )

    # --- Hadith search via full-text index ---
    remaining = max(0, limit - len(results))
    if remaining > 0:
        hadith_rows = _fulltext_hadith_search(neo4j, q, remaining)
        for r in hadith_rows:
            snippet = r.get("matn_en") or r["matn_ar"]
            results.append(
                SearchResult(
                    id=r["id"],
                    type="hadith",
                    title=snippet[:120] + "..." if len(snippet) > 120 else snippet,
                    title_ar=r["matn_ar"][:120],
                    score=r["score"],
                    collection=r.get("collection_name"),
                    grade=normalize_grade(r.get("grade")),
                    # Map the sparse free-text topic_tags onto the canonical topic
                    # vocabulary so the facet filters against a stable token set
                    # rather than fuzzy substrings. Empty = uncategorized/unknown.
                    topics=canonical_topics_for_tags(r.get("topic_tags")),
                )
            )

    # --- Saturating relevance transform (absolute confidence) ---
    # Neo4j's ``db.index.fulltext.queryNodes`` returns unbounded BM25-style
    # scores (commonly 1–10, but no upper bound). The frontend multiplies by 100
    # to render a percentage, so a raw score of 2.5 would display as "250%".
    #
    # ig#1065 bounded this with within-result-set max-normalisation, but that
    # forced the top hit of *every* query to exactly 100% regardless of how
    # strong the match actually was — the badge colour thresholds then read as
    # rank-within-result-set, not absolute confidence. ig#1070 replaces it with
    # ``score / (score + k)`` (monotonic, bounded [0, 1), top hit no longer pinned
    # to 1.0). ``k`` is configurable / calibration-pending — see ``SearchSettings``.
    if results:
        k = get_settings().search.relevance_saturation_k
        results = [r.model_copy(update={"score": saturate_relevance(r.score, k)}) for r in results]

    # --- Total count across both result types ---
    # The result list above is capped at ``limit``; ``total`` must reflect the
    # full count of matching narrators + hadiths so clients can paginate.
    total = _fulltext_narrator_count(neo4j, q) + _fulltext_hadith_count(neo4j, q)

    return SearchResultsResponse(results=results, total=total, query=q)


def _fulltext_narrator_search(neo4j: Neo4jClient, query: str, limit: int) -> list[dict[str, Any]]:
    """Search narrators using full-text index, falling back to CONTAINS."""
    try:
        return neo4j.execute_read(
            """
            CALL db.index.fulltext.queryNodes('narrator_search', $q)
            YIELD node, score
            RETURN node.id AS id, node.name_ar AS name_ar,
                   node.name_en AS name_en, node.death_year_ah AS death_year_ah, score
            LIMIT $limit
            """,
            {"q": query, "limit": limit},
        )
    except Exception:  # noqa: BLE001
        log.debug("fulltext narrator_search unavailable, falling back to CONTAINS")
        return neo4j.execute_read(
            """
            MATCH (n:Narrator)
            WHERE n.name_ar CONTAINS $q OR n.name_en CONTAINS $q
            RETURN n.id AS id, n.name_ar AS name_ar, n.name_en AS name_en,
                   n.death_year_ah AS death_year_ah, 1.0 AS score
            LIMIT $limit
            """,
            {"q": query, "limit": limit},
        )


def _fulltext_hadith_search(neo4j: Neo4jClient, query: str, limit: int) -> list[dict[str, Any]]:
    """Search hadiths using full-text index, falling back to CONTAINS."""
    # ``grade`` resolves the connected Grading node, falling back to the legacy
    # flat property, mirroring the hadiths route's ``_GRADE_EXPR``; the caller
    # normalizes it to a canonical token. ``collection_name`` and ``topic_tags``
    # feed the collection/topic facets. (#1036)
    try:
        return neo4j.execute_read(
            """
            CALL db.index.fulltext.queryNodes('hadith_search', $q)
            YIELD node, score
            OPTIONAL MATCH (node)-[:GRADED_BY]->(g:Grading)
            RETURN node.id AS id, node.matn_ar AS matn_ar,
                   node.matn_en AS matn_en, score,
                   node.collection_name AS collection_name,
                   node.topic_tags AS topic_tags,
                   coalesce(g.grade, node.grade_composite, node.grade) AS grade
            LIMIT $limit
            """,
            {"q": query, "limit": limit},
        )
    except Exception:  # noqa: BLE001
        log.debug("fulltext hadith_search unavailable, falling back to CONTAINS")
        return neo4j.execute_read(
            """
            MATCH (h:Hadith)
            WHERE h.matn_ar CONTAINS $q OR h.matn_en CONTAINS $q
            OPTIONAL MATCH (h)-[:GRADED_BY]->(g:Grading)
            RETURN h.id AS id, h.matn_ar AS matn_ar, h.matn_en AS matn_en,
                   1.0 AS score,
                   h.collection_name AS collection_name,
                   h.topic_tags AS topic_tags,
                   coalesce(g.grade, h.grade_composite, h.grade) AS grade
            LIMIT $limit
            """,
            {"q": query, "limit": limit},
        )


def _fulltext_narrator_count(neo4j: Neo4jClient, query: str) -> int:
    """Count all narrators matching the query, using the same index/fallback as search."""
    try:
        rows = neo4j.execute_read(
            """
            CALL db.index.fulltext.queryNodes('narrator_search', $q)
            YIELD node
            RETURN count(node) AS total
            """,
            {"q": query},
        )
    except Exception:  # noqa: BLE001
        log.debug("fulltext narrator_search unavailable, counting via CONTAINS")
        rows = neo4j.execute_read(
            """
            MATCH (n:Narrator)
            WHERE n.name_ar CONTAINS $q OR n.name_en CONTAINS $q
            RETURN count(n) AS total
            """,
            {"q": query},
        )
    return rows[0]["total"] if rows else 0


def _fulltext_hadith_count(neo4j: Neo4jClient, query: str) -> int:
    """Count all hadiths matching the query, using the same index/fallback as search."""
    try:
        rows = neo4j.execute_read(
            """
            CALL db.index.fulltext.queryNodes('hadith_search', $q)
            YIELD node
            RETURN count(node) AS total
            """,
            {"q": query},
        )
    except Exception:  # noqa: BLE001
        log.debug("fulltext hadith_search unavailable, counting via CONTAINS")
        rows = neo4j.execute_read(
            """
            MATCH (h:Hadith)
            WHERE h.matn_ar CONTAINS $q OR h.matn_en CONTAINS $q
            RETURN count(h) AS total
            """,
            {"q": query},
        )
    return rows[0]["total"] if rows else 0


@router.get("/search/semantic", response_model=SearchResultsResponse)
def search_semantic(
    q: str = Query(..., min_length=1, max_length=500, description="Semantic search query"),
    limit: int = Query(10, ge=1, le=50),
    pg: PgClient = Depends(get_pg),
) -> SearchResultsResponse:
    """Semantic similarity search using pgvector.

    Embeds the query with the configured embedder (see ``src/enrich/embeddings.py``)
    and cosine-ranks the ``isnad_graph.hadith_embeddings`` table against that
    vector. Returns 503 when the table or pgvector extension is unavailable.

    The query is embedded at request time rather than looked up by exact text:
    the previous implementation matched the query string against stored hadith
    text (``WHERE text = %s``), so anything but a verbatim hadith returned
    nothing even when embeddings were loaded (isnad-graph#1049).
    """
    query_vector = to_pgvector_literal(get_embedder().embed([q])[0])
    try:
        rows = pg.execute(
            """
            SELECT h.id, h.matn_ar, h.matn_en,
                   1 - (e.embedding <=> %s::vector) AS score
            FROM isnad_graph.hadith_embeddings e
            JOIN isnad_graph.hadiths h ON h.id = e.hadith_id
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
            """,
            (query_vector, query_vector, limit),
        )
        # Total count of candidate hadiths (the LIMIT above caps ``rows`` at
        # ``limit``; ``total`` must reflect the full searchable set).
        count_rows = pg.execute(
            """
            SELECT count(*) AS total
            FROM isnad_graph.hadith_embeddings e
            JOIN isnad_graph.hadiths h ON h.id = e.hadith_id
            """
        )
    except Exception:  # noqa: BLE001
        log.debug("pgvector semantic search unavailable", exc_info=True)
        return JSONResponse(  # type: ignore[return-value]
            status_code=503,
            content={
                "detail": "Semantic search is not yet available. pgvector backend required.",
                "query": q,
            },
        )

    # Facet metadata (collection/grade/topics) is intentionally left empty for
    # semantic hits: those attributes live on the Neo4j graph, not on the
    # ``isnad_graph.hadiths`` projection this query reads, and the search-page
    # matcher treats a missing value as "unknown, not excluded" — so facets do
    # not (yet) refine semantic results. (#1036)
    results: list[SearchResult] = []
    for r in rows:
        snippet = r.get("matn_en") or r["matn_ar"]
        # ``1 - cosine_distance`` is theoretically in [-1, 1]; clamp to [0, 1]
        # so a degenerate embedding never produces a negative relevance score.
        raw_score = float(r.get("score") or 0.0)
        results.append(
            SearchResult(
                id=r["id"],
                type="hadith",
                title=snippet[:120] + "..." if len(snippet) > 120 else snippet,
                title_ar=r["matn_ar"][:120],
                score=max(0.0, min(1.0, raw_score)),
            )
        )

    total = count_rows[0]["total"] if count_rows else len(results)
    return SearchResultsResponse(results=results, total=total, query=q)
