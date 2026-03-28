"""Migrate USER nodes from Neo4j to PostgreSQL users table.

Idempotent — safe to re-run. Uses ON CONFLICT to skip duplicates.
"""

from __future__ import annotations

import structlog

from src.auth.pg_users import ensure_users_table
from src.config import get_settings
from src.utils.neo4j_client import Neo4jClient
from src.utils.pg_client import PgClient

log = structlog.get_logger(logger_name=__name__)


def migrate_users() -> int:
    """Read all Neo4j USER nodes and insert into PostgreSQL.

    Returns the number of users migrated.
    """
    settings = get_settings()
    neo4j = Neo4jClient(
        uri=settings.neo4j.uri,
        user=settings.neo4j.user,
        password=settings.neo4j.password,
    )
    pg = PgClient()

    try:
        ensure_users_table(pg)

        records = neo4j.execute_read("MATCH (u:USER) RETURN u")
        log.info("neo4j_users_found", count=len(records))

        migrated = 0
        for rec in records:
            node = rec["u"]
            provider = node.get("provider", "unknown")
            provider_user_id = node.get("provider_user_id", node.get("id", ""))
            email = node.get("email")
            name = node.get("name", "")
            is_admin = node.get("is_admin", False)
            is_suspended = node.get("is_suspended", False)
            role = node.get("role")

            pg.execute(
                """
                INSERT INTO users (id, email, name, provider, provider_user_id,
                                   is_admin, is_suspended, role)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (provider, provider_user_id) DO NOTHING
                """,
                (email, name, provider, provider_user_id, is_admin, is_suspended, role),
            )
            migrated += 1

        pg_count = pg.execute("SELECT count(*) AS total FROM users")
        total = pg_count[0]["total"] if pg_count else 0
        log.info("migration_complete", migrated=migrated, pg_total=total, neo4j_total=len(records))
        return migrated
    finally:
        pg.close()
        neo4j.close()


if __name__ == "__main__":
    migrate_users()
