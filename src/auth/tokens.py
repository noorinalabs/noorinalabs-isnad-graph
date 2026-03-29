"""JWT token generation and validation with Redis-backed revocation."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import redis as redis_lib
from cachetools import TTLCache
from jose import JWTError, jwt

from src.config import get_settings
from src.utils.logging import get_logger
from src.utils.redis_client import get_redis_client

logger = get_logger(__name__)

# Bounded in-memory fallback with TTL matching access token lifetime (30 min)
_revoked_tokens: TTLCache[str, bool] = TTLCache(maxsize=10_000, ttl=1800)


def create_access_token(
    user_id: str, expires_minutes: int | None = None, role: str = "viewer"
) -> str:
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
        "role": role,
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


def _is_token_revoked(jti: str) -> bool | None:
    """Check if a token JTI has been revoked.

    Returns True if revoked, False if definitely not revoked, or None if
    revocation state cannot be reliably determined (Redis was expected but
    went down mid-operation and the token is not in the local cache).
    """
    redis_client = get_redis_client()
    if redis_client is not None:
        try:
            return bool(redis_client.exists(f"revoked_token:{jti}") > 0)
        except (redis_lib.ConnectionError, redis_lib.TimeoutError, OSError):  # fmt: skip
            logger.warning("Redis check failed, falling through to local cache")
            # Redis was reachable but failed — revocation state unreliable
            if jti in _revoked_tokens:
                return True
            logger.warning(
                "Revocation check unavailable: Redis down and token %s not in local cache",
                jti,
            )
            return None

    # Redis not configured/reachable — local cache is the only source
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
    if isinstance(jti, str):
        revoked = _is_token_revoked(jti)
        if revoked is True:
            raise ValueError("Token has been revoked")
        if revoked is None:
            raise ValueError("Revocation check unavailable — cannot verify token integrity")

    return payload


def revoke_token(token: str) -> bool:
    """Revoke a token by adding its JTI to the blacklist.

    Uses Redis with TTL matching token expiry for auto-cleanup.
    Falls back to in-memory cache if Redis is unavailable.

    Returns True if revocation was persisted reliably (Redis or local-only mode),
    False if Redis was expected but unavailable (revocation may not propagate
    across workers).
    """
    settings = get_settings().auth
    try:
        payload: dict[str, object] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return False
    jti = payload.get("jti")
    if not isinstance(jti, str):
        return False

    # Calculate TTL from token expiry
    exp = payload.get("exp")
    if isinstance(exp, int | float):
        ttl_seconds = max(int(exp - datetime.now(UTC).timestamp()), 1)
    else:
        # Default to refresh token expiry if no exp claim
        ttl_seconds = settings.refresh_token_expire_days * 86400

    redis_client = get_redis_client()
    if redis_client is not None:
        try:
            redis_client.setex(f"revoked_token:{jti}", ttl_seconds, "1")
            return True
        except (redis_lib.ConnectionError, redis_lib.TimeoutError, OSError):  # fmt: skip
            logger.warning("Redis revoke failed, falling back to in-memory blacklist")
            _revoked_tokens[jti] = True
            return False

    # Redis not configured — local cache is the only store
    _revoked_tokens[jti] = True
    return True
