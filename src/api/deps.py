"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Request

from src.utils.neo4j_client import Neo4jClient
from src.utils.pg_client import PgClient


def get_neo4j(request: Request) -> Neo4jClient:
    """Retrieve the Neo4j client from application state."""
    return request.app.state.neo4j  # type: ignore[no-any-return]


def get_bearer_token(request: Request) -> str:
    """Extract the raw Bearer token from the incoming ``Authorization`` header.

    Used to forward the admin's own user-service-issued JWT to downstream
    user-service calls (e.g. the relational audit log). Admin routes are gated
    by ``require_admin``, which has already validated a Bearer token is present,
    so this simply strips the scheme prefix.
    """
    auth_header = request.headers.get("Authorization", "")
    return auth_header.removeprefix("Bearer ")


def get_pg() -> Generator[PgClient]:
    """Yield a PgClient connection, closing it after the request."""
    client = PgClient()
    try:
        yield client
    finally:
        client.close()
