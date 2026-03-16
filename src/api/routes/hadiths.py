"""Hadith endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_neo4j
from src.api.models import HadithResponse, PaginatedResponse
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


@router.get("/hadiths", response_model=PaginatedResponse[HadithResponse])
def list_hadiths(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> PaginatedResponse[HadithResponse]:
    """Return a paginated list of hadiths."""
    skip = (page - 1) * limit
    count_result = neo4j.execute_read("MATCH (h:Hadith) RETURN count(h) AS total")
    total = count_result[0]["total"] if count_result else 0
    rows = neo4j.execute_read(
        "MATCH (h:Hadith) RETURN properties(h) AS props ORDER BY h.id SKIP $skip LIMIT $limit",
        {"skip": skip, "limit": limit},
    )
    items = [HadithResponse(**row["props"]) for row in rows]
    return PaginatedResponse(items=items, total=total, page=page, limit=limit)


@router.get("/hadiths/{hadith_id}", response_model=HadithResponse)
def get_hadith(
    hadith_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> HadithResponse:
    """Return a single hadith by ID."""
    rows = neo4j.execute_read(
        "MATCH (h:Hadith {id: $id}) RETURN properties(h) AS props",
        {"id": hadith_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Hadith '{hadith_id}' not found")
    return HadithResponse(**rows[0]["props"])
