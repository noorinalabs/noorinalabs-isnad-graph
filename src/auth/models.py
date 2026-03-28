"""Auth-related Pydantic models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    """Authenticated user."""

    model_config = ConfigDict(frozen=True)

    id: str
    email: str | None = None
    name: str
    provider: str
    provider_user_id: str
    created_at: datetime
    updated_at: datetime | None = None
    is_admin: bool = False
    is_suspended: bool = False
    role: str | None = None
    password_hash: str | None = None


class TokenResponse(BaseModel):
    """OAuth token pair response."""

    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthorizationUrlResponse(BaseModel):
    """Authorization URL for OAuth redirect."""

    model_config = ConfigDict(frozen=True)

    authorization_url: str


class RefreshRequest(BaseModel):
    """Refresh token request body."""

    model_config = ConfigDict(frozen=True)

    refresh_token: str
