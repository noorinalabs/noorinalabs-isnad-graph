"""Admin health check endpoints (liveness and readiness probes)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_neo4j
from src.api.models import SystemHealthResponse
from src.utils.neo4j_client import Neo4jClient

router = APIRouter(prefix="/health")


@router.get("/live", response_model=SystemHealthResponse)
def liveness() -> SystemHealthResponse:
    """Liveness probe — API is responding."""
    return SystemHealthResponse(
        status="ok",
        neo4j=True,
        postgres=True,
        redis=True,
    )


@router.get("/ready", response_model=SystemHealthResponse)
def readiness(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> SystemHealthResponse:
    """Readiness probe — check Neo4j, PostgreSQL, and Redis connectivity."""
    neo4j_ok = False
    pg_ok = False
    redis_ok = False

    try:
        neo4j.execute_read("RETURN 1 AS ok")
        neo4j_ok = True
    except Exception:
        pass

    try:
        from src.config import get_settings

        settings = get_settings()
        if settings.postgres.dsn:
            import psycopg2

            conn = psycopg2.connect(str(settings.postgres.dsn))
            conn.close()
            pg_ok = True
    except Exception:
        pass

    try:
        from src.config import get_settings

        settings = get_settings()
        if settings.redis.url:
            import redis

            r = redis.from_url(str(settings.redis.url))
            r.ping()
            redis_ok = True
    except Exception:
        pass

    all_ok = neo4j_ok and pg_ok and redis_ok
    return SystemHealthResponse(
        status="ok" if all_ok else "degraded",
        neo4j=neo4j_ok,
        postgres=pg_ok,
        redis=redis_ok,
    )
