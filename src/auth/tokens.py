"""JWT token generation and validation with Redis-backed revocation."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from src.config import get_settings

logger = logging.getLogger(__name__)

# In-memory fallback for when Redis is unavailable
_revoked_tokens: set[str] = set()


def _get_redis_client() -> Any | None:
    """Return a Redis client or None if unavailable."""
    try:
        import redis

        settings = get_settings().redis
        client = redis.Redis.from_url(settings.url, decode_responses=True)
        client.ping()
        return client
    except Exception:  # noqa: BLE001
        return None


def create_access_token(user_id: str, expires_minutes: int | None = None) -> str:
    """Create a JWT access token for the given user."""
    settings = get_settings().auth
    if expires_minutes is None:
        expires_minutes = settings.access_token_expire_minutes
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": secrets.token_hex(16),
    }
    return str(jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def create_refresh_token(user_id: str, expires_days: int | None = None) -> str:
    """Create a JWT refresh token for the given user."""
    settings = get_settings().auth
    if expires_days is None:
        expires_days = settings.refresh_token_expire_days
    expire = datetime.now(UTC) + timedelta(days=expires_days)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": secrets.token_hex(16),
    }
    return str(jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def _is_token_revoked(jti: str) -> bool:
    """Check if a token JTI has been revoked (Redis first, fallback to in-memory)."""
    redis_client = _get_redis_client()
    if redis_client is not None:
        try:
            return bool(redis_client.exists(f"revoked_token:{jti}") > 0)
        except Exception:  # noqa: BLE001
            logger.warning("Redis check failed, falling back to in-memory blacklist")
    return jti in _revoked_tokens


def verify_token(token: str) -> dict[str, object]:
    """Verify and decode a JWT token.

    Raises ValueError if the token is invalid, expired, or revoked.
    """
    settings = get_settings().auth
    try:
        payload: dict[str, object] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc

    jti = payload.get("jti")
    if isinstance(jti, str) and _is_token_revoked(jti):
        raise ValueError("Token has been revoked")

    return payload


def revoke_token(token: str) -> None:
    """Revoke a token by adding its JTI to the blacklist.

    Uses Redis with TTL matching token expiry for auto-cleanup.
    Falls back to in-memory set if Redis is unavailable.
    """
    settings = get_settings().auth
    try:
        payload: dict[str, object] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return
    jti = payload.get("jti")
    if not isinstance(jti, str):
        return

    # Calculate TTL from token expiry
    exp = payload.get("exp")
    if isinstance(exp, int | float):
        ttl_seconds = max(int(exp - datetime.now(UTC).timestamp()), 1)
    else:
        # Default to refresh token expiry if no exp claim
        ttl_seconds = settings.refresh_token_expire_days * 86400

    redis_client = _get_redis_client()
    if redis_client is not None:
        try:
            redis_client.setex(f"revoked_token:{jti}", ttl_seconds, "1")
            return
        except Exception:  # noqa: BLE001
            logger.warning("Redis revoke failed, falling back to in-memory blacklist")

    _revoked_tokens.add(jti)
