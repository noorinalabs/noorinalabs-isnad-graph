"""HTTP client for the user-service relational ``audit_log`` endpoints.

The admin audit trail lives in user-service's relational store (``audit_log``
table) rather than on Neo4j ``:AUDIT_LOG`` nodes (ig#1140). isnad-graph is a
*consumer* of that contract: it forwards the admin's own ``Authorization:
Bearer <jwt>`` header verbatim — user-service issued the token and validates it
itself, so no service-to-service credential is needed.

Calls are synchronous (matching the JWKS fetch in :mod:`src.api.auth`) with the
same 10s timeout, since the admin audit routes are sync handlers.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.config import get_settings

# Mirror the JWKS-fetch timeout in src.api.auth for consistency.
_TIMEOUT = 10.0


def _audit_url() -> str:
    """Return the user-service audit endpoint URL."""
    base = get_settings().auth.user_service_url.rstrip("/")
    return f"{base}/api/v1/audit"


def _auth_headers(token: str) -> dict[str, str]:
    """Build the forwarded Authorization header from the admin's bearer token."""
    return {"Authorization": f"Bearer {token}"}


def create_audit_log(
    token: str,
    *,
    action: str,
    actor_id: str,
    actor_name: str = "",
    target_user_id: str | None = None,
    details: str = "",
) -> dict[str, Any]:
    """POST a new audit entry to user-service, returning the created row.

    Forwards the admin's bearer token verbatim. Raises ``httpx.HTTPError`` if
    user-service is unreachable or returns a non-2xx status — callers decide
    whether that is fatal (see the best-effort handling in the purge route).
    """
    resp = httpx.post(
        _audit_url(),
        json={
            "action": action,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "target_user_id": target_user_id,
            "details": details,
        },
        headers=_auth_headers(token),
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]


def list_audit_logs(
    token: str,
    *,
    page: int,
    limit: int,
    action: str | None = None,
) -> dict[str, Any]:
    """GET a paginated page of audit entries from user-service.

    Forwards the admin's bearer token verbatim and the ``page``/``limit``/
    ``action`` filters. Raises ``httpx.HTTPError`` on transport/HTTP failure.
    """
    params: dict[str, str | int] = {"page": page, "limit": limit}
    if action:
        params["action"] = action
    resp = httpx.get(
        _audit_url(),
        params=params,
        headers=_auth_headers(token),
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[no-any-return]
