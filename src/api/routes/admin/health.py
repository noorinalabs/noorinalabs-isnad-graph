"""Admin health check endpoints (liveness and readiness probes)."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends

from src.api.deps import get_neo4j
from src.api.models import SystemHealthResponse
from src.utils.logging import get_logger
from src.utils.neo4j_client import Neo4jClient

router = APIRouter(prefix="/health")

log = get_logger(__name__)

_DSN_CREDENTIALS_RE = re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)[^@/\s]+(?=@)")


def _redact_dsn(text: str) -> str:
    """Strip ``user:password`` from any ``scheme://user:pass@host`` URI in *text*.

    Defensive — modern psycopg/redis don't leak credentials in error messages, but
    this guarantees the no-credentials-in-logs invariant even if a future library
    bump changes that behaviour.
    """
    return _DSN_CREDENTIALS_RE.sub(r"\g<scheme>***", text)


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

    All three probes log structured failures (with exception class) so degraded
    states are debuggable from logs. DSN credentials are redacted from any
    exception text that escapes into log messages.
    """
    neo4j_ok = False
    pg_ok = False
    redis_ok = False

    try:
        neo4j.execute_read("RETURN 1 AS ok")
        neo4j_ok = True
    except Exception as exc:
        log.error(
            "neo4j health probe failed",
            exc_type=type(exc).__name__,
            exc_msg=_redact_dsn(str(exc)),
        )

    try:
        from src.config import get_settings

        settings = get_settings()
        if settings.postgres.effective_dsn:
            import psycopg

            conn = psycopg.connect(str(settings.postgres.effective_dsn))
            conn.close()
            pg_ok = True
    except Exception as exc:
        log.error(
            "postgres health probe failed",
            exc_type=type(exc).__name__,
            exc_msg=_redact_dsn(str(exc)),
        )

    try:
        from src.config import get_settings

        settings = get_settings()
        if settings.redis.effective_url:
            import redis

            r = redis.from_url(str(settings.redis.effective_url))
            r.ping()
            redis_ok = True
    except Exception as exc:
        log.error(
            "redis health probe failed",
            exc_type=type(exc).__name__,
            exc_msg=_redact_dsn(str(exc)),
        )

    all_ok = neo4j_ok and pg_ok and redis_ok
    return SystemHealthResponse(
        status="ok" if all_ok else "degraded",
        neo4j=neo4j_ok,
        postgres=pg_ok,
        redis=redis_ok,
    )
