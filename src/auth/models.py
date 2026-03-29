"""Auth-related Pydantic models."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


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


class UserPublic(BaseModel):
    """User response model that excludes password_hash."""

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

    @staticmethod
    def from_user(user: User) -> UserPublic:
        """Create a UserPublic from a User, stripping password_hash."""
        return UserPublic(
            id=user.id,
            email=user.email,
            name=user.name,
            provider=user.provider,
            provider_user_id=user.provider_user_id,
            created_at=user.created_at,
            updated_at=user.updated_at,
            is_admin=user.is_admin,
            is_suspended=user.is_suspended,
            role=user.role,
        )


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


class RegisterRequest(BaseModel):
    """Email/password registration request body."""

    model_config = ConfigDict(frozen=True)

    email: str
    password: str
    name: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            msg = "Invalid email format"
            raise ValueError(msg)
        if len(v) > 320:
            msg = "Email must not exceed 320 characters"
            raise ValueError(msg)
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            msg = "Password must be at least 8 characters"
            raise ValueError(msg)
        if len(v) > 128:
            msg = "Password must not exceed 128 characters"
            raise ValueError(msg)
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            msg = "Name must not be empty"
            raise ValueError(msg)
        if len(v) > 255:
            msg = "Name must not exceed 255 characters"
            raise ValueError(msg)
        return v


class EmailLoginRequest(BaseModel):
    """Email/password login request body."""

    model_config = ConfigDict(frozen=True)

    email: str
    password: str


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
