"""Admin system configuration management endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_pg
from src.api.middleware import require_admin
from src.api.models import (
    FORBIDDEN_CONFIG_KEYS,
    ConfigAuditEntry,
    ConfigAuditResponse,
    SystemConfig,
    SystemConfigUpdate,
)
from src.auth.models import User
from src.utils.pg_client import PgClient

router = APIRouter(prefix="/config")

# SQL for idempotent table creation
_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS system_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS config_audit (
    id         BIGSERIAL PRIMARY KEY,
    key        TEXT NOT NULL,
    old_value  TEXT NOT NULL,
    new_value  TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# Default config instance
_DEFAULTS = SystemConfig()


def _ensure_tables(pg: PgClient) -> None:
    """Create config tables if they don't exist (idempotent)."""
    pg.execute(_CREATE_TABLES_SQL)


def _load_config(pg: PgClient) -> SystemConfig:
    """Load current config from DB, falling back to defaults for missing keys."""
    _ensure_tables(pg)
    rows = pg.execute("SELECT key, value FROM system_config")
    db_values: dict[str, str] = {r["key"]: r["value"] for r in rows}

    defaults = _DEFAULTS.model_dump()
    merged: dict[str, Any] = {}
    for field_name, default_value in defaults.items():
        if field_name in db_values:
            raw = db_values[field_name]
            if isinstance(default_value, (dict, list)):
                merged[field_name] = json.loads(raw)
            elif isinstance(default_value, int):
                merged[field_name] = int(raw)
            else:
                merged[field_name] = raw
        else:
            merged[field_name] = default_value

    return SystemConfig(**merged)


def _serialize_value(value: object) -> str:
    """Serialize a config value for storage."""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


@router.get("", response_model=SystemConfig)
def get_config(
    pg: PgClient = Depends(get_pg),
) -> SystemConfig:
    """Return the current system configuration."""
    return _load_config(pg)


@router.patch("", response_model=SystemConfig)
def update_config(
    body: SystemConfigUpdate,
    admin: User = Depends(require_admin),
    pg: PgClient = Depends(get_pg),
) -> SystemConfig:
    """Update system configuration. Only non-null fields are applied."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Reject any attempt to set secret keys
    for key in updates:
        if key in FORBIDDEN_CONFIG_KEYS:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot set secret key via config API: {key}",
            )

    _ensure_tables(pg)

    # Load current values for audit trail
    current = _load_config(pg).model_dump()

    for key, new_value in updates.items():
        old_serialized = _serialize_value(current.get(key, ""))
        new_serialized = _serialize_value(new_value)

        # Upsert into system_config
        pg.execute(
            """
            INSERT INTO system_config (key, value, updated_by, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = EXCLUDED.updated_at
            """,
            (key, new_serialized, admin.id),
        )

        # Append to audit log (append-only, no deletion)
        pg.execute(
            """
            INSERT INTO config_audit (key, old_value, new_value, changed_by, changed_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (key, old_serialized, new_serialized, admin.id),
        )

    return _load_config(pg)


@router.get("/audit", response_model=ConfigAuditResponse)
def config_audit(
    pg: PgClient = Depends(get_pg),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
) -> ConfigAuditResponse:
    """Return the append-only config change audit log."""
    _ensure_tables(pg)

    count_rows = pg.execute("SELECT count(*) AS total FROM config_audit")
    total = count_rows[0]["total"] if count_rows else 0

    offset = (page - 1) * limit
    rows = pg.execute(
        """
        SELECT key, old_value, new_value, changed_by,
               changed_at::text AS changed_at
        FROM config_audit
        ORDER BY changed_at DESC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    )

    entries = [
        ConfigAuditEntry(
            key=r["key"],
            old_value=r["old_value"],
            new_value=r["new_value"],
            changed_by=r["changed_by"],
            changed_at=r["changed_at"],
        )
        for r in rows
    ]

    return ConfigAuditResponse(entries=entries, total=total)
