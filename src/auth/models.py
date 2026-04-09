"""Auth-related Pydantic models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    """User roles with hierarchical privilege levels."""

    VIEWER = "viewer"
    EDITOR = "editor"
    MODERATOR = "moderator"
    ADMIN = "admin"


ROLE_HIERARCHY: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.EDITOR: 1,
    Role.MODERATOR: 2,
    Role.ADMIN: 3,
}


class User(BaseModel):
    """Authenticated user context built from user-service JWT claims."""

    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    role: str | None = None
    is_admin: bool = False
    subscription_status: str | None = None
