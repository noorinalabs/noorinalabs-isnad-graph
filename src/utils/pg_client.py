"""PostgreSQL client with psycopg 3 and dict-row support."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_settings
from src.utils.logging import get_logger

__all__ = ["PgClient"]

log = get_logger(__name__)


class PgClient:
    """Context-managed psycopg 3 wrapper.

    Falls back to ``get_settings()`` when *dsn* is omitted.
    """

    def __init__(self, dsn: str | None = None) -> None:
        settings = get_settings()
        self._dsn = dsn or settings.postgres.dsn
        try:
            self._conn: psycopg.Connection[dict[str, Any]] = psycopg.connect(
                self._dsn, row_factory=dict_row
            )
        except psycopg.Error as exc:
            # Log host portion only — never leak credentials.
            log.error(
                "pg_connect_failed",
                dsn=self._dsn.split("@")[-1],
                error=str(exc),
            )
            raise
        log.info("pg_connected", dsn=self._dsn.split("@")[-1])

    # --- queries ---------------------------------------------------------

    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        """Execute *query* and return rows as dicts (empty list for DML)."""
        try:
            with self._conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:
                    return [dict(row) for row in cur.fetchall()]
                self._conn.commit()
                return []
        except psycopg.Error as exc:
            self._conn.rollback()
            log.error("pg_execute_failed", query=query, error=str(exc))
            raise

    def execute_many(self, query: str, params_list: list[tuple[Any, ...]]) -> int:
        """Execute *query* for each parameter tuple. Returns ``rowcount``."""
        try:
            with self._conn.cursor() as cur:
                cur.executemany(query, params_list)
                self._conn.commit()
                return cur.rowcount
        except psycopg.Error as exc:
            self._conn.rollback()
            log.error("pg_execute_many_failed", query=query, error=str(exc))
            raise

    # --- schema ----------------------------------------------------------

    def ensure_schema(self) -> None:
        """Create the ``isnad_graph`` schema and ``vector`` extension (idempotent)."""
        self.execute("CREATE SCHEMA IF NOT EXISTS isnad_graph")
        self.execute("CREATE EXTENSION IF NOT EXISTS vector")
        log.info("pg_schema_ensured")

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()
        log.info("pg_disconnected")

    def __enter__(self) -> PgClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
