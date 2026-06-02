"""Health check and public status endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Response

from src.api.deps import get_neo4j
from src.api.models import HealthResponse, ServiceStatus, StatusResponse
from src.utils.neo4j_client import Neo4jClient
from src.utils.pg_client import PgClient
from src.utils.redis_client import get_redis_client

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
    """Check PostgreSQL connectivity and return status.

    Uses the application's ``PgClient`` wrapper — the same accessor used for
    real traffic — instead of hand-rolling a raw ``psycopg.connect`` call.
    """
    start = time.monotonic()
    try:
        with PgClient() as pg:
            rows = pg.execute("SELECT version() AS version")
        latency = (time.monotonic() - start) * 1000
        raw = rows[0]["version"] if rows else None
        version = str(raw).split(",")[0] if raw else None
        return ServiceStatus(status="up", latency_ms=round(latency, 1), version=version)
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return ServiceStatus(status="down", latency_ms=round(latency, 1), error=str(exc))


def _check_redis() -> ServiceStatus:
    """Check Redis connectivity and return status.

    Uses the shared ``get_redis_client`` helper — the same accessor used for
    real traffic — instead of hand-rolling a raw ``redis.from_url`` call.
    """
    start = time.monotonic()
    try:
        client = get_redis_client()
        if client is None:
            latency = (time.monotonic() - start) * 1000
            return ServiceStatus(
                status="down", latency_ms=round(latency, 1), error="redis unavailable"
            )
        info: dict[str, object] = client.info("server")
        version = str(info.get("redis_version", "")) or None
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
