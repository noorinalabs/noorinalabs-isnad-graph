"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_neo4j
from src.api.models import HealthResponse
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


@router.get("/", response_model=HealthResponse)
def health_check(neo4j: Neo4jClient = Depends(get_neo4j)) -> HealthResponse:
    """Return API health status with Neo4j connectivity."""
    try:
        neo4j.execute_read("RETURN 1 AS ok")
        connected = True
    except Exception:
        connected = False
    return HealthResponse(status="ok", neo4j_connected=connected)
