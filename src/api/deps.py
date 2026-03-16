"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from src.utils.neo4j_client import Neo4jClient


def get_neo4j(request: Request) -> Neo4jClient:
    """Retrieve the Neo4j client from application state."""
    return request.app.state.neo4j  # type: ignore[no-any-return]
