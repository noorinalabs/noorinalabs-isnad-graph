"""Authentication module — JWT validation via user-service JWKS."""

from __future__ import annotations

from src.auth.jwks import fetch_jwks, invalidate_jwks_cache, verify_user_service_token
from src.auth.models import ROLE_HIERARCHY, Role, User

__all__ = [
    "ROLE_HIERARCHY",
    "Role",
    "User",
    "fetch_jwks",
    "invalidate_jwks_cache",
    "verify_user_service_token",
]
