"""Admin health check endpoints (liveness and readiness probes)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_neo4j
from src.api.models import SystemHealthResponse
from src.utils.neo4j_client import Neo4jClient
from src.utils.pg_client import PgClient
from src.utils.redis_client import get_redis_client

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
    """Readiness probe — check Neo4j, PostgreSQL, and Redis connectivity.

    Verifies each service through the same accessor the application uses for
    real traffic — the ``app.state.neo4j`` driver, the ``PgClient`` wrapper,
    and ``get_redis_client`` — rather than constructing throwaway connections
    by hand. The accessors are still invoked inside per-service guards so an
    unreachable dependency yields a ``degraded`` response rather than a 500.
    """
    neo4j_ok = False
    pg_ok = False
    redis_ok = False

    try:
        neo4j.execute_read("RETURN 1 AS ok")
        neo4j_ok = True
    except Exception:
        pass

    try:
        with PgClient() as pg:
            pg.execute("SELECT 1")
        pg_ok = True
    except Exception:
        pass

    try:
        client = get_redis_client()
        if client is not None:
            client.ping()
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
