"""Tests for the health check and status endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _patch_pg_and_redis():
    """Return context managers that mock PostgreSQL and Redis for the health checks.

    Both are mocked at the names imported into the health module — the
    ``PgClient`` wrapper and the ``get_redis_client`` helper — so the route
    exercises the same accessors the application uses for real traffic.
    ``PgClient`` is used as a context manager, so the mock's ``__enter__``
    returns the connection mock.
    """
    mock_pg = MagicMock()
    mock_pg.execute.return_value = [{"version": "PostgreSQL 16.2"}]
    mock_pg_cls = MagicMock()
    mock_pg_cls.return_value.__enter__.return_value = mock_pg

    mock_r = MagicMock()
    mock_r.ping.return_value = True
    mock_r.info.return_value = {"redis_version": "7.2.4"}

    pg_patch = patch("src.api.routes.health.PgClient", mock_pg_cls)
    redis_patch = patch("src.api.routes.health.get_redis_client", return_value=mock_r)
    return pg_patch, redis_patch, mock_pg, mock_r


def test_health_check_all_up(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /health returns 200 with healthy status when all services are up."""
    mock_neo4j.execute_read.return_value = [{"version": "5.26.0"}]
    pg_patch, redis_patch, _mock_pg, _mock_r = _patch_pg_and_redis()
    with pg_patch, redis_patch:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["services"]["neo4j"]["status"] == "up"
    assert body["services"]["postgres"]["status"] == "up"
    assert body["services"]["redis"]["status"] == "up"


def test_health_check_neo4j_down(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /health returns 503 when Neo4j is down."""
    mock_neo4j.execute_read.side_effect = RuntimeError("connection refused")
    pg_patch, redis_patch, _mock_pg, _mock_r = _patch_pg_and_redis()
    with pg_patch, redis_patch:
        resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["services"]["neo4j"]["status"] == "down"
    assert body["services"]["neo4j"]["error"] is not None


def test_health_check_postgres_down(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /health returns 503 when PostgreSQL is unreachable via get_pg."""
    mock_neo4j.execute_read.return_value = [{"version": "5.26.0"}]
    pg_patch, redis_patch, mock_pg, _mock_r = _patch_pg_and_redis()
    mock_pg.execute.side_effect = RuntimeError("connection refused")
    with pg_patch, redis_patch:
        resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["services"]["postgres"]["status"] == "down"
    assert body["services"]["postgres"]["error"] is not None


def test_health_check_redis_unavailable(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /health returns 503 when get_redis_client yields None."""
    mock_neo4j.execute_read.return_value = [{"version": "5.26.0"}]
    pg_patch, _redis_patch, _mock_pg, _mock_r = _patch_pg_and_redis()
    redis_none = patch("src.api.routes.health.get_redis_client", return_value=None)
    with pg_patch, redis_none:
        resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["services"]["redis"]["status"] == "down"


def test_root_serves_health(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET / serves the same health check as /health."""
    mock_neo4j.execute_read.return_value = [{"version": "5.26.0"}]
    pg_patch, redis_patch, _mock_pg, _mock_r = _patch_pg_and_redis()
    with pg_patch, redis_patch:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"


def test_status_all_operational(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /status returns operational when all services are up."""
    mock_neo4j.execute_read.return_value = [{"version": "5.26.0"}]
    pg_patch, redis_patch, _mock_pg, _mock_r = _patch_pg_and_redis()
    with pg_patch, redis_patch:
        resp = client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "operational"
    assert body["message"] == "All systems operational."


def test_status_degraded(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /status returns degraded when a service is down."""
    mock_neo4j.execute_read.side_effect = RuntimeError("connection refused")
    pg_patch, redis_patch, _mock_pg, _mock_r = _patch_pg_and_redis()
    with pg_patch, redis_patch:
        resp = client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert "neo4j" in body["message"]
