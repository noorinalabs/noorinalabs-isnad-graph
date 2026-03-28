"""PostgreSQL user storage — CRUD operations for the users table."""

from __future__ import annotations

import uuid
from typing import Any

from src.auth.models import User
from src.utils.pg_client import PgClient


def ensure_users_table(pg: PgClient) -> None:
    """Create the users table and indexes (idempotent)."""
    pg.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email           VARCHAR(320),
            name            VARCHAR(255) NOT NULL,
            provider        VARCHAR(50) NOT NULL,
            provider_user_id VARCHAR(255) NOT NULL,
            password_hash   VARCHAR(255),
            is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
            is_suspended    BOOLEAN NOT NULL DEFAULT FALSE,
            role            VARCHAR(100),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (provider, provider_user_id)
        )
    """)
    pg.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email) WHERE email IS NOT NULL"
    )


def upsert_user(
    pg: PgClient,
    *,
    provider: str,
    provider_user_id: str,
    email: str | None,
    name: str,
) -> User:
    """Insert a new user or update name/email on conflict. Returns the user."""
    rows = pg.execute(
        """
        INSERT INTO users (id, email, name, provider, provider_user_id)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (provider, provider_user_id) DO UPDATE
            SET email = COALESCE(EXCLUDED.email, users.email),
                name = EXCLUDED.name,
                updated_at = now()
        RETURNING id, email, name, provider, provider_user_id, password_hash,
                  is_admin, is_suspended, role, created_at, updated_at
        """,
        (str(uuid.uuid4()), email, name, provider, provider_user_id),
    )
    return _row_to_user(rows[0])


def get_user_by_id(pg: PgClient, user_id: str) -> User | None:
    """Fetch a single user by UUID."""
    rows = pg.execute(
        """
        SELECT id, email, name, provider, provider_user_id, password_hash,
               is_admin, is_suspended, role, created_at, updated_at
        FROM users WHERE id = %s
        """,
        (user_id,),
    )
    return _row_to_user(rows[0]) if rows else None


def list_users(
    pg: PgClient,
    *,
    page: int = 1,
    limit: int = 20,
    search: str | None = None,
    role: str | None = None,
) -> tuple[list[User], int]:
    """Return a paginated list of users with optional filters."""
    where_parts: list[str] = []
    params: list[Any] = []

    if search:
        where_parts.append("(name ILIKE %s OR email ILIKE %s)")
        like = f"%{search}%"
        params.extend([like, like])
    if role:
        where_parts.append("role = %s")
        params.append(role)

    where = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    count_rows = pg.execute(f"SELECT count(*) AS total FROM users {where}", tuple(params))
    total: int = count_rows[0]["total"] if count_rows else 0

    offset = (page - 1) * limit
    rows = pg.execute(
        f"""
        SELECT id, email, name, provider, provider_user_id, password_hash,
               is_admin, is_suspended, role, created_at, updated_at
        FROM users {where}
        ORDER BY created_at DESC
        OFFSET %s LIMIT %s
        """,
        (*params, offset, limit),
    )
    return [_row_to_user(r) for r in rows], total


def update_user(
    pg: PgClient,
    user_id: str,
    *,
    is_admin: bool | None = None,
    is_suspended: bool | None = None,
    role: str | None = None,
) -> User | None:
    """Partial update of user fields. Returns updated user or None if not found."""
    set_parts: list[str] = []
    params: list[Any] = []

    if is_admin is not None:
        set_parts.append("is_admin = %s")
        params.append(is_admin)
    if is_suspended is not None:
        set_parts.append("is_suspended = %s")
        params.append(is_suspended)
    if role is not None:
        set_parts.append("role = %s")
        params.append(role)

    if not set_parts:
        return get_user_by_id(pg, user_id)

    set_parts.append("updated_at = now()")
    params.append(user_id)

    rows = pg.execute(
        f"""
        UPDATE users SET {", ".join(set_parts)}
        WHERE id = %s
        RETURNING id, email, name, provider, provider_user_id, password_hash,
                  is_admin, is_suspended, role, created_at, updated_at
        """,
        tuple(params),
    )
    return _row_to_user(rows[0]) if rows else None


def _row_to_user(row: dict[str, Any]) -> User:
    """Convert a PG row dict to a User model."""
    return User(
        id=str(row["id"]),
        email=row.get("email"),
        name=row["name"],
        provider=row["provider"],
        provider_user_id=row["provider_user_id"],
        password_hash=row.get("password_hash"),
        is_admin=row.get("is_admin", False),
        is_suspended=row.get("is_suspended", False),
        role=row.get("role"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at"),
    )
