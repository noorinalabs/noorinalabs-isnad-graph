"""OAuth authentication module."""

from __future__ import annotations

from src.auth.models import ROLE_HIERARCHY, Role, TokenResponse, User
from src.auth.providers import PROVIDERS, OAuthProvider, OAuthUserInfo, get_provider
from src.auth.sessions import (
    SessionInfo,
    create_session,
    destroy_all_user_sessions,
    destroy_session,
    get_session,
    list_user_sessions,
    touch_session,
)
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
    "SessionInfo",
    "TokenResponse",
    "User",
    "create_access_token",
    "create_refresh_token",
    "create_session",
    "destroy_all_user_sessions",
    "destroy_session",
    "get_provider",
    "get_session",
    "list_user_sessions",
    "revoke_token",
    "touch_session",
    "verify_token",
]
