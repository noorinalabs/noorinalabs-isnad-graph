"""JWT token generation and validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from src.config import get_settings

# In-memory set of revoked JTIs (for production, use Redis or database)
_revoked_tokens: set[str] = set()


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
    }
    return str(jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def create_refresh_token(user_id: str, expires_days: int | None = None) -> str:
    """Create a JWT refresh token for the given user."""
    import secrets

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
    if isinstance(jti, str) and jti in _revoked_tokens:
        raise ValueError("Token has been revoked")

    return payload


def revoke_token(token: str) -> None:
    """Revoke a token by adding its JTI to the revoked set."""
    settings = get_settings().auth
    try:
        payload: dict[str, object] = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        return
    jti = payload.get("jti")
    if isinstance(jti, str):
        _revoked_tokens.add(jti)
