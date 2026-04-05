"""Narrator endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_neo4j
from src.api.models import NarratorResponse, PaginatedResponse
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


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
    and returns results ranked by relevance score.
    """
    skip = (page - 1) * limit

    if q:
        # Use the fulltext index (narrator_search) on [name_ar, name_en].
        # Wrap in quotes for phrase matching; escape embedded quotes.
        escaped = q.replace("\\", "\\\\").replace('"', '\\"')
        search_term = f'"{escaped}"'

        count_result = neo4j.execute_read(
            "CALL db.index.fulltext.queryNodes('narrator_search', $term) "
            "YIELD node RETURN count(node) AS total",
            {"term": search_term},
        )
        total = count_result[0]["total"] if count_result else 0

        rows = neo4j.execute_read(
            "CALL db.index.fulltext.queryNodes('narrator_search', $term) "
            "YIELD node, score "
            "RETURN properties(node) AS props "
            "ORDER BY score DESC SKIP $skip LIMIT $limit",
            {"term": search_term, "skip": skip, "limit": limit},
        )
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
