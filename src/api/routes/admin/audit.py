"""Admin audit log endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from src.api.deps import get_neo4j
from src.api.models import PaginatedResponse
from src.utils.neo4j_client import Neo4jClient

router = APIRouter(prefix="/audit")


class AuditLogEntry(BaseModel):
    """A single audit log entry for admin actions."""

    model_config = ConfigDict(frozen=True)

    id: str
    action: str
    target_user_id: str | None = None
    actor_id: str
    actor_name: str = ""
    details: str = ""
    created_at: str


class AuditLogCreateRequest(BaseModel):
    """Request to create an audit log entry (internal use)."""

    model_config = ConfigDict(frozen=True)

    action: str
    target_user_id: str | None = None
    actor_id: str
    actor_name: str = ""
    details: str = ""


@router.get("", response_model=PaginatedResponse[AuditLogEntry])
def list_audit_logs(
    neo4j: Neo4jClient = Depends(get_neo4j),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    action: str | None = Query(None),
) -> PaginatedResponse[AuditLogEntry]:
    """List admin audit log entries with optional action filter."""
    params: dict[str, object] = {"skip": (page - 1) * limit, "limit": limit}
    where_clauses: list[str] = []

    if action:
        where_clauses.append("a.action = $action")
        params["action"] = action

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_query = f"MATCH (a:AUDIT_LOG) {where} RETURN count(a) AS total"
    count_result = neo4j.execute_read(count_query, params)
    total = count_result[0]["total"] if count_result else 0

    query = f"""
        MATCH (a:AUDIT_LOG) {where}
        RETURN a ORDER BY a.created_at DESC
        SKIP $skip LIMIT $limit
    """
    records = neo4j.execute_read(query, params)

    items = [
        AuditLogEntry(
            id=r["a"]["id"],
            action=r["a"].get("action", ""),
            target_user_id=r["a"].get("target_user_id"),
            actor_id=r["a"].get("actor_id", ""),
            actor_name=r["a"].get("actor_name", ""),
            details=r["a"].get("details", ""),
            created_at=str(r["a"].get("created_at", "")),
        )
        for r in records
    ]

    return PaginatedResponse[AuditLogEntry](items=items, total=total, page=page, limit=limit)


def create_audit_entry(
    neo4j: Neo4jClient,
    action: str,
    actor_id: str,
    actor_name: str = "",
    target_user_id: str | None = None,
    details: str = "",
) -> None:
    """Create an audit log entry in Neo4j."""
    query = """
        CREATE (a:AUDIT_LOG {
            id: randomUUID(),
            action: $action,
            actor_id: $actor_id,
            actor_name: $actor_name,
            target_user_id: $target_user_id,
            details: $details,
            created_at: datetime()
        })
    """
    neo4j.execute_write(
        query,
        {
            "action": action,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "target_user_id": target_user_id,
            "details": details,
        },
    )
