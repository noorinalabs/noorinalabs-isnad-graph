"""Admin user management endpoints.

User CRUD operations are now handled by user-service. This module is
retained as a stub so that existing admin router registration does not
break.  All endpoints return 501 directing callers to user-service.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/users")

_GONE_DETAIL = "User management has moved to user-service. Use the user-service admin API."


@router.get("")
def list_users() -> None:
    """User listing has moved to user-service."""
    raise HTTPException(status_code=501, detail=_GONE_DETAIL)


@router.get("/{user_id}")
def get_user(user_id: str) -> None:
    """User lookup has moved to user-service."""
    raise HTTPException(status_code=501, detail=_GONE_DETAIL)


@router.patch("/{user_id}")
def update_user(user_id: str) -> None:
    """User update has moved to user-service."""
    raise HTTPException(status_code=501, detail=_GONE_DETAIL)


@router.patch("/{user_id}/role")
def update_user_role(user_id: str) -> None:
    """User role update has moved to user-service."""
    raise HTTPException(status_code=501, detail=_GONE_DETAIL)
