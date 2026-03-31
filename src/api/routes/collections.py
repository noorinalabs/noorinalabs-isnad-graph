"""Collection endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_neo4j
from src.api.models import CollectionResponse, PaginatedResponse
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


def _row_to_response(props: dict[str, Any]) -> CollectionResponse:
    """Build a CollectionResponse from Neo4j node properties.

    Uses ``.get()`` with defaults so that missing or null properties on the
    Neo4j node don't cause a Pydantic validation error (500).
    """
    return CollectionResponse(
        id=props.get("id", ""),
        name_ar=props.get("name_ar", ""),
        name_en=props.get("name_en", ""),
        compiler_name=props.get("compiler_name"),
        compiler_id=props.get("compiler_id"),
        compilation_year_ah=props.get("compilation_year_ah"),
        sect=props.get("sect", ""),
        canonical_rank=props.get("canonical_rank"),
        total_hadiths=props.get("total_hadiths"),
        book_count=props.get("book_count"),
    )


@router.get("/collections", response_model=PaginatedResponse[CollectionResponse])
def list_collections(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> PaginatedResponse[CollectionResponse]:
    """Return paginated collections."""
    skip = (page - 1) * limit

    count_rows = neo4j.execute_read(
        "MATCH (c:Collection) RETURN count(c) AS total",
    )
    total = count_rows[0]["total"] if count_rows else 0

    rows = neo4j.execute_read(
        "MATCH (c:Collection) RETURN properties(c) AS props ORDER BY c.id SKIP $skip LIMIT $limit",
        {"skip": skip, "limit": limit},
    )
    items = [_row_to_response(row["props"]) for row in rows]
    return PaginatedResponse[CollectionResponse](items=items, total=total, page=page, limit=limit)


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
def get_collection(
    collection_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> CollectionResponse:
    """Return a single collection by ID."""
    rows = neo4j.execute_read(
        "MATCH (c:Collection {id: $id}) RETURN properties(c) AS props",
        {"id": collection_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found")
    return _row_to_response(rows[0]["props"])
