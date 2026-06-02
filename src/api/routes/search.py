"""Search endpoints: full-text and semantic."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from src.api.deps import get_neo4j, get_pg
from src.api.models import SearchResult, SearchResultsResponse
from src.utils.neo4j_client import Neo4jClient
from src.utils.pg_client import PgClient

router = APIRouter()

log = logging.getLogger(__name__)


@router.get("/search", response_model=SearchResultsResponse)
def search(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> SearchResultsResponse:
    """Full-text search across hadiths and narrators.

    Uses Neo4j full-text indexes (``narrator_search``, ``hadith_search``)
    when available, falling back to ``CONTAINS`` substring matching.
    """
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
                )
            )

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
                   node.name_en AS name_en, score
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
                   1.0 AS score
            LIMIT $limit
            """,
            {"q": query, "limit": limit},
        )


def _fulltext_hadith_search(neo4j: Neo4jClient, query: str, limit: int) -> list[dict[str, Any]]:
    """Search hadiths using full-text index, falling back to CONTAINS."""
    try:
        return neo4j.execute_read(
            """
            CALL db.index.fulltext.queryNodes('hadith_search', $q)
            YIELD node, score
            RETURN node.id AS id, node.matn_ar AS matn_ar,
                   node.matn_en AS matn_en, score
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
            RETURN h.id AS id, h.matn_ar AS matn_ar, h.matn_en AS matn_en,
                   1.0 AS score
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

    Queries the ``isnad_graph.hadith_embeddings`` table for cosine-similar
    hadiths.  Returns 503 when the table or pgvector extension is unavailable.
    """
    try:
        rows = pg.execute(
            """
            SELECT h.id, h.matn_ar, h.matn_en,
                   1 - (e.embedding <=> (
                       SELECT embedding FROM isnad_graph.hadith_embeddings
                       WHERE text = %s LIMIT 1
                   )) AS score
            FROM isnad_graph.hadith_embeddings e
            JOIN isnad_graph.hadiths h ON h.id = e.hadith_id
            ORDER BY e.embedding <=> (
                SELECT embedding FROM isnad_graph.hadith_embeddings
                WHERE text = %s LIMIT 1
            )
            LIMIT %s
            """,
            (q, q, limit),
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

    results: list[SearchResult] = []
    for r in rows:
        snippet = r.get("matn_en") or r["matn_ar"]
        results.append(
            SearchResult(
                id=r["id"],
                type="hadith",
                title=snippet[:120] + "..." if len(snippet) > 120 else snippet,
                title_ar=r["matn_ar"][:120],
                score=float(r.get("score") or 0.0),
            )
        )

    total = count_rows[0]["total"] if count_rows else len(results)
    return SearchResultsResponse(results=results, total=total, query=q)
