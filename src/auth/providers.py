"""OAuth provider abstraction layer."""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import redis as redis_lib

from src.config import get_settings
from src.utils.redis_client import get_redis_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OAuthUserInfo:
    """Normalized user info returned by an OAuth provider."""

    provider: str
    provider_user_id: str
    email: str
    name: str
    avatar_url: str | None = None


def _generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    import base64

    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


# --- PKCE Verifier Storage (Redis with in-memory fallback) ---

_pkce_store: dict[str, tuple[str, float]] = {}
_PKCE_TTL_SECONDS = 600  # 10 minutes
_PKCE_MAX_ENTRIES = 10000


def _evict_expired_pkce() -> None:
    """Remove expired entries from the in-memory PKCE store."""
    now = time.monotonic()
    expired = [k for k, (_, ts) in _pkce_store.items() if now - ts > _PKCE_TTL_SECONDS]
    for k in expired:
        del _pkce_store[k]


def store_pkce_verifier(state: str, verifier: str) -> None:
    """Store PKCE code_verifier keyed by OAuth state parameter."""
    redis_client = get_redis_client()
    if redis_client is not None:
        try:
            redis_client.setex(f"pkce:{state}", _PKCE_TTL_SECONDS, verifier)
            return
        except (redis_lib.ConnectionError, redis_lib.TimeoutError, OSError):  # fmt: skip
            logger.warning("Redis PKCE store failed, using in-memory fallback")
    _evict_expired_pkce()
    if len(_pkce_store) >= _PKCE_MAX_ENTRIES:
        logger.warning("PKCE in-memory store at capacity (%d), evicting oldest", _PKCE_MAX_ENTRIES)
        oldest = min(_pkce_store, key=lambda k: _pkce_store[k][1])
        del _pkce_store[oldest]
    _pkce_store[state] = (verifier, time.monotonic())


def retrieve_pkce_verifier(state: str) -> str | None:
    """Retrieve and delete the PKCE code_verifier for the given state."""
    redis_client = get_redis_client()
    if redis_client is not None:
        try:
            pipe = redis_client.pipeline()
            pipe.get(f"pkce:{state}")
            pipe.delete(f"pkce:{state}")
            results = pipe.execute()
            value: str | None = results[0]
            return value
        except (redis_lib.ConnectionError, redis_lib.TimeoutError, OSError):  # fmt: skip
            logger.warning("Redis PKCE retrieve failed, trying in-memory fallback")
    entry = _pkce_store.pop(state, None)
    if entry is None:
        return None
    verifier, ts = entry
    if time.monotonic() - ts > _PKCE_TTL_SECONDS:
        return None
    return verifier


# --- Apple JWKS Cache ---

_apple_jwks_cache: dict[str, object] | None = None
_apple_jwks_fetched_at: float = 0.0
_APPLE_JWKS_TTL_SECONDS = 86400  # 24 hours
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"


async def _get_apple_jwks() -> dict[str, object]:
    """Fetch Apple's public JWKS keys, cached for 24 hours."""
    global _apple_jwks_cache, _apple_jwks_fetched_at  # noqa: PLW0603
    now = time.monotonic()
    if _apple_jwks_cache is not None and (now - _apple_jwks_fetched_at) < _APPLE_JWKS_TTL_SECONDS:
        return _apple_jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(APPLE_JWKS_URL)
        resp.raise_for_status()
        _apple_jwks_cache = resp.json()
        _apple_jwks_fetched_at = now
        return _apple_jwks_cache


class OAuthProvider(ABC):
    """Common interface for all OAuth providers."""

    @abstractmethod
    def get_authorization_url(self, redirect_uri: str, state: str) -> tuple[str, str]:
        """Return (authorization_url, pkce_code_verifier)."""
        ...

    @abstractmethod
    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> OAuthUserInfo:
        """Exchange authorization code for user info."""
        ...


class GoogleProvider(OAuthProvider):
    """Google OAuth2 provider."""

    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def get_authorization_url(self, redirect_uri: str, state: str) -> tuple[str, str]:
        settings = get_settings().auth
        verifier, challenge = _generate_pkce()
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}", verifier

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> OAuthUserInfo:
        settings = get_settings().auth
        token_data: dict[str, str] = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            token_data["code_verifier"] = code_verifier
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(self.TOKEN_URL, data=token_data)
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]

            user_resp = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_resp.raise_for_status()
            data = user_resp.json()

        return OAuthUserInfo(
            provider="google",
            provider_user_id=data["sub"],
            email=data["email"],
            name=data.get("name", data["email"]),
            avatar_url=data.get("picture"),
        )


class AppleProvider(OAuthProvider):
    """Apple Sign-In provider."""

    AUTHORIZE_URL = "https://appleid.apple.com/auth/authorize"
    TOKEN_URL = "https://appleid.apple.com/auth/token"

    def get_authorization_url(self, redirect_uri: str, state: str) -> tuple[str, str]:
        settings = get_settings().auth
        verifier, challenge = _generate_pkce()
        params = {
            "client_id": settings.apple_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "name email",
            "state": state,
            "response_mode": "form_post",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}", verifier

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> OAuthUserInfo:
        settings = get_settings().auth
        token_data: dict[str, str] = {
            "client_id": settings.apple_client_id,
            "client_secret": settings.apple_client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            token_data["code_verifier"] = code_verifier
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(self.TOKEN_URL, data=token_data)
            token_resp.raise_for_status()
            id_token = token_resp.json()["id_token"]

        # Verify Apple ID token signature against Apple's public JWKS
        from jose import jwt as jose_jwt

        jwks = await _get_apple_jwks()
        claims = jose_jwt.decode(
            id_token,
            jwks,
            algorithms=["RS256"],
            audience=settings.apple_client_id,
            issuer="https://appleid.apple.com",
        )

        return OAuthUserInfo(
            provider="apple",
            provider_user_id=claims["sub"],
            email=claims.get("email", ""),
            name=claims.get("email", ""),
        )


class FacebookProvider(OAuthProvider):
    """Facebook OAuth2 provider."""

    AUTHORIZE_URL = "https://www.facebook.com/v19.0/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
    USERINFO_URL = "https://graph.facebook.com/v19.0/me"

    def get_authorization_url(self, redirect_uri: str, state: str) -> tuple[str, str]:
        settings = get_settings().auth
        verifier, challenge = _generate_pkce()
        params = {
            "client_id": settings.facebook_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "email,public_profile",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}", verifier

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> OAuthUserInfo:
        settings = get_settings().auth
        params: dict[str, str] = {
            "client_id": settings.facebook_client_id,
            "client_secret": settings.facebook_client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            params["code_verifier"] = code_verifier
        async with httpx.AsyncClient() as client:
            token_resp = await client.get(self.TOKEN_URL, params=params)
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]

            user_resp = await client.get(
                self.USERINFO_URL,
                params={
                    "fields": "id,name,email,picture",
                    "access_token": access_token,
                },
            )
            user_resp.raise_for_status()
            data = user_resp.json()

        return OAuthUserInfo(
            provider="facebook",
            provider_user_id=data["id"],
            email=data.get("email", ""),
            name=data.get("name", ""),
            avatar_url=data.get("picture", {}).get("data", {}).get("url"),
        )


class GitHubProvider(OAuthProvider):
    """GitHub OAuth2 provider."""

    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USERINFO_URL = "https://api.github.com/user"
    EMAIL_URL = "https://api.github.com/user/emails"

    def get_authorization_url(self, redirect_uri: str, state: str) -> tuple[str, str]:
        settings = get_settings().auth
        verifier, challenge = _generate_pkce()
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}", verifier

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> OAuthUserInfo:
        settings = get_settings().auth
        token_data: dict[str, str] = {
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            token_data["code_verifier"] = code_verifier
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                self.TOKEN_URL,
                data=token_data,
                headers={"Accept": "application/json"},
            )
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }
            user_resp = await client.get(self.USERINFO_URL, headers=headers)
            user_resp.raise_for_status()
            data = user_resp.json()

            email = data.get("email", "")
            if not email:
                email_resp = await client.get(self.EMAIL_URL, headers=headers)
                email_resp.raise_for_status()
                emails = email_resp.json()
                primary = next((e for e in emails if e.get("primary")), None)
                email = primary["email"] if primary else emails[0]["email"]

        return OAuthUserInfo(
            provider="github",
            provider_user_id=str(data["id"]),
            email=email,
            name=data.get("name") or data.get("login", ""),
            avatar_url=data.get("avatar_url"),
        )


PROVIDERS: dict[str, type[OAuthProvider]] = {
    "google": GoogleProvider,
    "apple": AppleProvider,
    "facebook": FacebookProvider,
    "github": GitHubProvider,
}


def get_provider(name: str) -> OAuthProvider:
    """Get a configured provider instance by name.

    Raises ValueError if the provider is not registered.
    """
    provider_cls = PROVIDERS.get(name)
    if provider_cls is None:
        raise ValueError(f"Unknown OAuth provider: {name}")
    return provider_cls()
