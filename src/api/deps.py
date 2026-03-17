"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Request

from src.utils.neo4j_client import Neo4jClient
from src.utils.pg_client import PgClient


def get_neo4j(request: Request) -> Neo4jClient:
    """Retrieve the Neo4j client from application state."""
    return request.app.state.neo4j  # type: ignore[no-any-return]


def get_pg() -> Generator[PgClient]:
    """Yield a PgClient connection, closing it after the request."""
    client = PgClient()
    try:
        yield client
    finally:
        client.close()
