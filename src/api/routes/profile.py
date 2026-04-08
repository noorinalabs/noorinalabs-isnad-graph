"""User profile and session management endpoints.

Profile data is sourced from the JWT claims (user-service). Session
management uses the Redis-backed session store in ``src.auth.sessions``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from src.api.middleware import require_auth
from src.auth.models import User
from src.auth.sessions import (
    SessionInfo,
    destroy_session,
    list_user_sessions,
)

router = APIRouter(prefix="/users/me")


class UserPreferences(BaseModel):
    """User preferences (placeholder until user-service preferences API)."""

    model_config = ConfigDict(frozen=True)

    default_search_mode: str = "fulltext"
    results_per_page: int = 20
    language_preference: str = "en"
    theme_preference: str = "system"


class UserProfileResponse(BaseModel):
    """User profile derived from JWT claims."""

    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    role: str | None = None
    is_admin: bool = False
    preferences: UserPreferences


@router.get("/profile", response_model=UserProfileResponse)
def get_profile(
    user: User = Depends(require_auth),
) -> UserProfileResponse:
    """Return the profile for the current user (from JWT claims)."""
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_admin=user.is_admin,
        preferences=UserPreferences(),
    )


class SessionResponse(BaseModel):
    """An active session entry."""

    model_config = ConfigDict(frozen=True)

    id: str
    created_at: str
    last_active: str
    ip_address: str | None = None
    user_agent: str | None = None
    is_current: bool = False


def _session_to_response(info: SessionInfo) -> SessionResponse:
    return SessionResponse(
        id=info.session_id,
        created_at=str(info.created_at),
        last_active=str(info.last_active),
        ip_address=info.ip_address or None,
        user_agent=info.user_agent or None,
        is_current=False,
    )


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    user: User = Depends(require_auth),
) -> list[SessionResponse]:
    """List active sessions for the current user (from Redis)."""
    sessions = list_user_sessions(user.id)
    return [_session_to_response(s) for s in sessions]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: str,
    user: User = Depends(require_auth),
) -> None:
    """Revoke a specific session for the current user."""
    # Verify the session belongs to the requesting user
    sessions = list_user_sessions(user.id)
    if not any(s.session_id == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="Session not found")

    destroy_session(session_id)
    return None
