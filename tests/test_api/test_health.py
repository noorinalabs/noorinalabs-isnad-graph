"""Tests for the health check and status endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _patch_pg_and_redis():
    """Return context managers that mock PostgreSQL and Redis in the health module."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = ("PostgreSQL 16.2",)
    mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    mock_r = MagicMock()
    mock_r.ping.return_value = True
    mock_r.info.return_value = {"redis_version": "7.2.4"}

    pg_patch = patch("src.api.routes.health.psycopg")
    redis_patch = patch("src.api.routes.health.redis_lib")
    return pg_patch, redis_patch, mock_conn, mock_r


def test_health_check_all_up(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /health returns 200 with healthy status when all services are up."""
    mock_neo4j.execute_read.return_value = [{"version": "5.26.0"}]
    pg_patch, redis_patch, mock_conn, mock_r = _patch_pg_and_redis()
    with pg_patch as mock_psycopg, redis_patch as mock_redis:
        mock_psycopg.connect.return_value = mock_conn
        mock_redis.from_url.return_value = mock_r
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
    pg_patch, redis_patch, mock_conn, mock_r = _patch_pg_and_redis()
    with pg_patch as mock_psycopg, redis_patch as mock_redis:
        mock_psycopg.connect.return_value = mock_conn
        mock_redis.from_url.return_value = mock_r
        resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["services"]["neo4j"]["status"] == "down"
    assert body["services"]["neo4j"]["error"] is not None


def test_root_serves_health(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET / serves the same health check as /health."""
    mock_neo4j.execute_read.return_value = [{"version": "5.26.0"}]
    pg_patch, redis_patch, mock_conn, mock_r = _patch_pg_and_redis()
    with pg_patch as mock_psycopg, redis_patch as mock_redis:
        mock_psycopg.connect.return_value = mock_conn
        mock_redis.from_url.return_value = mock_r
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"


def test_status_all_operational(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /status returns operational when all services are up."""
    mock_neo4j.execute_read.return_value = [{"version": "5.26.0"}]
    pg_patch, redis_patch, mock_conn, mock_r = _patch_pg_and_redis()
    with pg_patch as mock_psycopg, redis_patch as mock_redis:
        mock_psycopg.connect.return_value = mock_conn
        mock_redis.from_url.return_value = mock_r
        resp = client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "operational"
    assert body["message"] == "All systems operational."


def test_status_degraded(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /status returns degraded when a service is down."""
    mock_neo4j.execute_read.side_effect = RuntimeError("connection refused")
    pg_patch, redis_patch, mock_conn, mock_r = _patch_pg_and_redis()
    with pg_patch as mock_psycopg, redis_patch as mock_redis:
        mock_psycopg.connect.return_value = mock_conn
        mock_redis.from_url.return_value = mock_r
        resp = client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert "neo4j" in body["message"]
