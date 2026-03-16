"""OAuth authentication module."""

from __future__ import annotations

from src.auth.models import TokenResponse, User
from src.auth.providers import PROVIDERS, OAuthProvider, OAuthUserInfo, get_provider
from src.auth.tokens import create_access_token, create_refresh_token, verify_token

__all__ = [
    "PROVIDERS",
    "OAuthProvider",
    "OAuthUserInfo",
    "TokenResponse",
    "User",
    "create_access_token",
    "create_refresh_token",
    "get_provider",
    "verify_token",
]
