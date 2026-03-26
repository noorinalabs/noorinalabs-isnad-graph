"""Health check and public status endpoints."""

from __future__ import annotations

import time

import psycopg
import redis as redis_lib
from fastapi import APIRouter, Depends, Response

from src.api.deps import get_neo4j
from src.api.models import HealthResponse, ServiceStatus, StatusResponse
from src.config import get_settings
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


def _check_neo4j(neo4j: Neo4jClient) -> ServiceStatus:
    """Check Neo4j connectivity and return status."""
    start = time.monotonic()
    try:
        result = neo4j.execute_read(
            "CALL dbms.components() YIELD name, versions RETURN versions[0] AS version"
        )
        latency = (time.monotonic() - start) * 1000
        version = result[0]["version"] if result else None
        return ServiceStatus(status="up", latency_ms=round(latency, 1), version=version)
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return ServiceStatus(status="down", latency_ms=round(latency, 1), error=str(exc))


def _check_postgres() -> ServiceStatus:
    """Check PostgreSQL connectivity and return status."""
    start = time.monotonic()
    try:
        settings = get_settings()
        conn = psycopg.connect(settings.postgres.dsn)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                row = cur.fetchone()
                version = str(row[0]).split(",")[0] if row else None
        finally:
            conn.close()
        latency = (time.monotonic() - start) * 1000
        return ServiceStatus(status="up", latency_ms=round(latency, 1), version=version)
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return ServiceStatus(status="down", latency_ms=round(latency, 1), error=str(exc))


def _check_redis() -> ServiceStatus:
    """Check Redis connectivity and return status."""
    start = time.monotonic()
    try:
        settings = get_settings()
        r = redis_lib.from_url(str(settings.redis.url))
        r.ping()
        info: dict[str, object] = r.info("server")  # type: ignore[assignment]
        version = str(info.get("redis_version", "")) or None
        r.close()
        latency = (time.monotonic() - start) * 1000
        return ServiceStatus(status="up", latency_ms=round(latency, 1), version=version)
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return ServiceStatus(status="down", latency_ms=round(latency, 1), error=str(exc))


@router.get("/", include_in_schema=False)
@router.get("/health", response_model=HealthResponse)
def health_check(
    response: Response,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> HealthResponse:
    """Comprehensive health check — returns per-service status.

    Returns HTTP 200 when all services are healthy, 503 when degraded.
    """
    services = {
        "neo4j": _check_neo4j(neo4j),
        "postgres": _check_postgres(),
        "redis": _check_redis(),
    }
    all_up = all(s.status == "up" for s in services.values())
    overall = "healthy" if all_up else "degraded"
    if not all_up:
        response.status_code = 503
    return HealthResponse(status=overall, services=services)


@router.get("/status", response_model=StatusResponse)
def public_status(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> StatusResponse:
    """Public-facing status summary — lightweight, no auth required."""
    services = {
        "neo4j": _check_neo4j(neo4j),
        "postgres": _check_postgres(),
        "redis": _check_redis(),
    }
    all_up = all(s.status == "up" for s in services.values())
    down_services = [name for name, s in services.items() if s.status != "up"]
    if all_up:
        return StatusResponse(status="operational", message="All systems operational.")
    return StatusResponse(
        status="degraded",
        message=f"Service(s) degraded: {', '.join(down_services)}.",
    )
