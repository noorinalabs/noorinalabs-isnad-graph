"""Narrator endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_neo4j
from src.api.models import NarratorResponse, PaginatedResponse
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()

log = logging.getLogger(__name__)


def _search_narrators(
    neo4j: Neo4jClient, q: str, skip: int, limit: int
) -> tuple[int, list[dict[str, Any]]]:
    """Search narrators by ``q``, returning ``(total, rows)``.

    Prefers the ``narrator_search`` full-text index (ranked by relevance) and
    falls back to a parameterized ``CONTAINS`` match when the index is absent
    (e.g. not yet created on a freshly provisioned graph). Both branches issue a
    single query that returns the full match count via ``size()`` plus the
    requested page slice, so the endpoint never 500s on a missing index.
    """
    try:
        # Quote the term so the Lucene parser treats it as a phrase and special
        # characters in user input don't break query parsing.
        escaped = q.replace("\\", "\\\\").replace('"', '\\"')
        search_term = f'"{escaped}"'
        result = neo4j.execute_read(
            "CALL db.index.fulltext.queryNodes('narrator_search', $term) "
            "YIELD node, score "
            "WITH node, score ORDER BY score DESC "
            "WITH collect({props: properties(node)}) AS all_rows "
            "RETURN size(all_rows) AS total, "
            "all_rows[$skip .. $skip + $limit] AS rows",
            {"term": search_term, "skip": skip, "limit": limit},
        )
    except Exception:  # noqa: BLE001 — degrade on any index/query failure
        log.debug("fulltext narrator_search unavailable, falling back to CONTAINS")
        result = neo4j.execute_read(
            "MATCH (n:Narrator) "
            "WHERE n.name_ar CONTAINS $q OR n.name_en CONTAINS $q "
            "WITH n ORDER BY n.id "
            "WITH collect({props: properties(n)}) AS all_rows "
            "RETURN size(all_rows) AS total, "
            "all_rows[$skip .. $skip + $limit] AS rows",
            {"q": q, "skip": skip, "limit": limit},
        )
    total = result[0]["total"] if result else 0
    rows = result[0]["rows"] if result else []
    return total, rows


@router.get("/narrators", response_model=PaginatedResponse[NarratorResponse])
def list_narrators(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, min_length=1, max_length=200),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> PaginatedResponse[NarratorResponse]:
    """Return a paginated list of narrators, optionally filtered by search query.

    When the ``q`` parameter is provided the endpoint queries the
    ``narrator_search`` full-text index (covers ``name_ar`` and ``name_en``)
    and returns results ranked by relevance score. If that index is not present
    on the graph the endpoint degrades to a ``CONTAINS`` substring match rather
    than returning a 500.
    """
    skip = (page - 1) * limit

    if q:
        total, rows = _search_narrators(neo4j, q, skip, limit)
    else:
        count_result = neo4j.execute_read(
            "MATCH (n:Narrator) RETURN count(n) AS total",
        )
        total = count_result[0]["total"] if count_result else 0

        rows = neo4j.execute_read(
            "MATCH (n:Narrator) RETURN properties(n) AS props "
            "ORDER BY n.id SKIP $skip LIMIT $limit",
            {"skip": skip, "limit": limit},
        )

    items = [NarratorResponse(**row["props"]) for row in rows]
    return PaginatedResponse(items=items, total=total, page=page, limit=limit)


@router.get("/narrators/{narrator_id}", response_model=NarratorResponse)
def get_narrator(
    narrator_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> NarratorResponse:
    """Return a single narrator by ID."""
    rows = neo4j.execute_read(
        "MATCH (n:Narrator {id: $id}) RETURN properties(n) AS props",
        {"id": narrator_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Narrator '{narrator_id}' not found")
    return NarratorResponse(**rows[0]["props"])
