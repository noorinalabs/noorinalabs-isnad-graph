"""OAuth authentication module."""

from __future__ import annotations

from src.auth.models import ROLE_HIERARCHY, Role, TokenResponse, User
from src.auth.providers import PROVIDERS, OAuthProvider, OAuthUserInfo, get_provider
from src.auth.tokens import (
    create_access_token,
    create_refresh_token,
    revoke_token,
    verify_token,
)

__all__ = [
    "PROVIDERS",
    "ROLE_HIERARCHY",
    "OAuthProvider",
    "OAuthUserInfo",
    "Role",
    "TokenResponse",
    "User",
    "create_access_token",
    "create_refresh_token",
    "get_provider",
    "revoke_token",
    "verify_token",
]
