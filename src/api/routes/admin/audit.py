"""Admin audit log endpoints.

The admin audit trail is owned by user-service's relational ``audit_log`` table
(ig#1140). isnad-graph no longer stores ``:AUDIT_LOG`` nodes on Neo4j — this
route is a thin consumer that forwards the admin's own bearer token to the
user-service audit API and maps the response back into the ``PaginatedResponse``
shape the admin frontend already consumes (path + shape unchanged).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from src.api import audit_client
from src.api.deps import get_bearer_token
from src.api.models import PaginatedResponse

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


@router.get("", response_model=PaginatedResponse[AuditLogEntry])
def list_audit_logs(
    token: str = Depends(get_bearer_token),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    action: str | None = Query(None),
) -> PaginatedResponse[AuditLogEntry]:
    """List admin audit log entries from user-service, newest first.

    Forwards the admin's bearer token and the ``page``/``limit``/``action``
    filters to user-service, then maps its ``audit_log`` rows into the same
    paginated shape the admin frontend consumes.
    """
    data = audit_client.list_audit_logs(token, page=page, limit=limit, action=action)

    items = [
        AuditLogEntry(
            id=str(row["id"]),
            action=row.get("action", ""),
            target_user_id=row.get("target_user_id"),
            actor_id=str(row.get("actor_id", "")),
            actor_name=row.get("actor_name", ""),
            details=row.get("details", ""),
            created_at=str(row.get("created_at", "")),
        )
        for row in data.get("items", [])
    ]

    return PaginatedResponse[AuditLogEntry](
        items=items,
        total=data.get("total", len(items)),
        page=data.get("page", page),
        limit=data.get("limit", limit),
    )


def create_audit_entry(
    token: str,
    action: str,
    actor_id: str,
    actor_name: str = "",
    target_user_id: str | None = None,
    details: str = "",
) -> None:
    """Record an admin audit entry in user-service's relational ``audit_log``.

    POSTs to the user-service audit API, forwarding the admin's bearer token
    (``token``) verbatim. Raises ``httpx.HTTPError`` if user-service is
    unreachable or rejects the request; the caller decides whether that is
    fatal (the purge route treats it as best-effort — see ``data.purge_source``).
    """
    audit_client.create_audit_log(
        token,
        action=action,
        actor_id=actor_id,
        actor_name=actor_name,
        target_user_id=target_user_id,
        details=details,
    )
