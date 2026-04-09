"""User profile endpoints.

Profile data is sourced from the JWT claims (user-service). Session
management has been migrated to user-service.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from src.api.middleware import require_auth
from src.auth.models import User

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
