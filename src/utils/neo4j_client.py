"""Neo4j graph database client with batch write support."""

from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase
from neo4j import exceptions as neo4j_exc

from src.config import get_settings
from src.utils.logging import get_logger

__all__ = ["Neo4jClient"]

log = get_logger(__name__)


class Neo4jClient:
    """Context-managed Neo4j driver wrapper.

    Falls back to ``get_settings()`` when constructor args are omitted,
    allowing easy overrides in tests.
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        settings = get_settings()
        self._uri = uri or settings.neo4j.uri
        self._user = user or settings.neo4j.user
        self._password = password or settings.neo4j.password
        try:
            self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
        except neo4j_exc.Neo4jError as exc:
            log.error("neo4j_connect_failed", uri=self._uri, error=str(exc))
            raise
        log.info("neo4j_connected", uri=self._uri)

    # --- reads -----------------------------------------------------------

    def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a read transaction and return a list of record dicts."""
        try:
            with self._driver.session() as session:
                return session.execute_read(lambda tx: list(tx.run(query, parameters or {}).data()))
        except neo4j_exc.Neo4jError as exc:
            log.error("neo4j_read_failed", query=query, error=str(exc))
            raise

    # --- writes ----------------------------------------------------------

    def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Run a single write transaction and return a list of record dicts."""
        try:
            with self._driver.session() as session:
                return session.execute_write(
                    lambda tx: list(tx.run(query, parameters or {}).data())
                )
        except neo4j_exc.Neo4jError as exc:
            log.error("neo4j_write_failed", query=query, error=str(exc))
            raise

    def execute_write_batch(
        self,
        query: str,
        batch: list[dict[str, Any]],
        batch_size: int = 1000,
    ) -> int:
        """Execute a parameterized write in batches.

        The *query* must use ``UNWIND $batch AS row`` to iterate over items.
        Returns the total number of nodes and relationships created.
        """
        total = 0
        for i in range(0, len(batch), batch_size):
            chunk = batch[i : i + batch_size]
            try:
                with self._driver.session() as session:
                    summary = session.execute_write(
                        lambda tx, c=chunk: tx.run(query, batch=c).consume()  # type: ignore[misc]
                    )
                    total += summary.counters.nodes_created + summary.counters.relationships_created
            except neo4j_exc.Neo4jError as exc:
                log.error(
                    "neo4j_batch_failed",
                    query=query,
                    offset=i,
                    error=str(exc),
                )
                raise
        return total

    # --- schema ----------------------------------------------------------

    def ensure_constraints(self) -> None:
        """Create uniqueness constraints for all node types (idempotent)."""
        node_types = [
            "Narrator",
            "Hadith",
            "Collection",
            "Chain",
            "Grading",
            "HistoricalEvent",
            "Location",
        ]
        for node_type in node_types:
            query = f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{node_type}) REQUIRE n.id IS UNIQUE"
            self.execute_write(query)
            log.info("constraint_ensured", node_type=node_type)

    # --- lifecycle -------------------------------------------------------

    def close(self) -> None:
        """Close the underlying driver."""
        self._driver.close()
        log.info("neo4j_disconnected")

    def __enter__(self) -> Neo4jClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
