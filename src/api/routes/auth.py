"""Authentication endpoints for OAuth login flows."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException

from src.api.middleware import require_auth
from src.auth.models import AuthorizationUrlResponse, RefreshRequest, TokenResponse, User
from src.auth.providers import PROVIDERS, get_provider, retrieve_pkce_verifier, store_pkce_verifier
from src.auth.tokens import create_access_token, create_refresh_token, revoke_token, verify_token
from src.config import get_settings

router = APIRouter()


def _build_redirect_uri(provider: str) -> str:
    """Build the OAuth callback redirect URI from settings."""
    base = get_settings().auth.oauth_redirect_base_url.rstrip("/")
    return f"{base}/api/v1/auth/callback/{provider}"


@router.post(
    "/auth/login/{provider}",
    response_model=AuthorizationUrlResponse,
)
def login(provider: str) -> AuthorizationUrlResponse:
    """Initiate OAuth flow — return the provider's authorization URL."""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    oauth_provider = get_provider(provider)
    state = secrets.token_urlsafe(32)
    redirect_uri = _build_redirect_uri(provider)
    url, verifier = oauth_provider.get_authorization_url(redirect_uri=redirect_uri, state=state)

    # Persist PKCE verifier so the callback can use it
    store_pkce_verifier(state, verifier)

    return AuthorizationUrlResponse(authorization_url=url)


@router.get("/auth/callback/{provider}", response_model=TokenResponse)
async def callback(provider: str, code: str, state: str) -> TokenResponse:
    """Handle OAuth callback — exchange code for tokens."""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    oauth_provider = get_provider(provider)
    redirect_uri = _build_redirect_uri(provider)

    # Retrieve PKCE verifier stored during login
    code_verifier = retrieve_pkce_verifier(state)

    try:
        user_info = await oauth_provider.exchange_code(
            code=code, redirect_uri=redirect_uri, code_verifier=code_verifier
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OAuth exchange failed: {exc}") from exc

    # Use provider + provider_user_id as the internal user ID
    user_id = f"{user_info.provider}:{user_info.provider_user_id}"
    settings = get_settings().auth

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest) -> TokenResponse:
    """Refresh an access token using a valid refresh token (with rotation)."""
    try:
        payload = verify_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")  # noqa: B904

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Revoke the old refresh token (rotation)
    revoke_token(body.refresh_token)

    settings = get_settings().auth
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/auth/logout", status_code=204)
def logout(user: User = Depends(require_auth)) -> None:
    """Invalidate the current session (revoke tokens)."""
    # In a full implementation, we'd revoke the refresh token from a store.
    # The access token is short-lived and will expire naturally.
    return None


@router.get("/auth/me", response_model=User)
def me(user: User = Depends(require_auth)) -> User:
    """Return the current authenticated user."""
    return user
