"""OAuth provider abstraction layer."""

from __future__ import annotations

import hashlib
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from src.config import get_settings


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


class OAuthProvider(ABC):
    """Common interface for all OAuth providers."""

    @abstractmethod
    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Return the provider's authorization URL."""
        ...

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo:
        """Exchange authorization code for user info."""
        ...


class GoogleProvider(OAuthProvider):
    """Google OAuth2 provider."""

    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        settings = get_settings().auth
        _verifier, challenge = _generate_pkce()
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo:
        settings = get_settings().auth
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
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

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        settings = get_settings().auth
        _verifier, challenge = _generate_pkce()
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
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo:
        settings = get_settings().auth
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": settings.apple_client_id,
                    "client_secret": settings.apple_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            id_token = token_resp.json()["id_token"]

            # Decode Apple ID token (unverified for claims extraction)
            from jose import jwt as jose_jwt

            claims = jose_jwt.get_unverified_claims(id_token)

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

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        settings = get_settings().auth
        _verifier, challenge = _generate_pkce()
        params = {
            "client_id": settings.facebook_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "email,public_profile",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo:
        settings = get_settings().auth
        async with httpx.AsyncClient() as client:
            token_resp = await client.get(
                self.TOKEN_URL,
                params={
                    "client_id": settings.facebook_client_id,
                    "client_secret": settings.facebook_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
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

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        settings = get_settings().auth
        _verifier, challenge = _generate_pkce()
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthUserInfo:
        settings = get_settings().auth
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
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
