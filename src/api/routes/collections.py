"""Collection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_neo4j
from src.api.models import CollectionResponse
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


@router.get("/collections", response_model=list[CollectionResponse])
def list_collections(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> list[CollectionResponse]:
    """Return all collections."""
    rows = neo4j.execute_read(
        "MATCH (c:Collection) RETURN properties(c) AS props ORDER BY c.id",
    )
    return [CollectionResponse(**row["props"]) for row in rows]


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
    return CollectionResponse(**rows[0]["props"])
