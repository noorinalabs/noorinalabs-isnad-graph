"""Authentication endpoints for OAuth login flows."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from src.api.middleware import require_auth
from src.auth.models import User
from src.auth.providers import PROVIDERS, get_provider, retrieve_pkce_verifier, store_pkce_verifier
from src.auth.tokens import create_access_token, create_refresh_token, revoke_token, verify_token
from src.config import get_settings
from src.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter()

_OAUTH_STATE_COOKIE = "oauth_state"


def _set_token_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    """Set httpOnly access and refresh token cookies on a response."""
    settings = get_settings().auth
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/",
    )


def _build_redirect_uri(provider: str) -> str:
    """Build the OAuth callback redirect URI from settings."""
    base = get_settings().auth.oauth_redirect_base_url.rstrip("/")
    return f"{base}/api/v1/auth/callback/{provider}"


@router.post("/auth/login/{provider}")
def login(provider: str) -> JSONResponse:
    """Initiate OAuth flow — return the provider's authorization URL."""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    log.info("oauth_login_initiated", provider=provider)
    oauth_provider = get_provider(provider)
    state = secrets.token_urlsafe(32)
    redirect_uri = _build_redirect_uri(provider)
    url, verifier = oauth_provider.get_authorization_url(redirect_uri=redirect_uri, state=state)

    # Persist PKCE verifier so the callback can use it
    store_pkce_verifier(state, verifier)

    settings = get_settings().auth
    response = JSONResponse(content={"authorization_url": url})
    response.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


@router.get("/auth/callback/{provider}")
async def callback(provider: str, code: str, state: str, request: Request) -> JSONResponse:
    """Handle OAuth callback — exchange code for tokens."""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # Validate state parameter against session cookie (CSRF protection)
    cookie_state = request.cookies.get(_OAUTH_STATE_COOKIE)
    if not cookie_state or not secrets.compare_digest(cookie_state, state):
        log.warning("oauth_state_mismatch", provider=provider)
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state — possible CSRF attack. Please retry login.",
        )

    oauth_provider = get_provider(provider)
    redirect_uri = _build_redirect_uri(provider)

    # Retrieve PKCE verifier stored during login
    code_verifier = retrieve_pkce_verifier(state)

    try:
        user_info = await oauth_provider.exchange_code(
            code=code, redirect_uri=redirect_uri, code_verifier=code_verifier
        )
    except Exception:
        log.exception("oauth_code_exchange_failed", provider=provider)
        raise HTTPException(  # noqa: B904
            status_code=400, detail="OAuth authentication failed. Please try again."
        )

    # Use provider + provider_user_id as the internal user ID
    user_id = f"{user_info.provider}:{user_info.provider_user_id}"

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    response = JSONResponse(content={"status": "ok"})
    _set_token_cookies(response, access_token, refresh_token)
    # Clear the one-time-use oauth_state cookie
    response.delete_cookie(_OAUTH_STATE_COOKIE, path="/")
    return response


@router.post("/auth/refresh")
def refresh(request: Request) -> JSONResponse:
    """Refresh an access token using the httpOnly refresh_token cookie (with rotation)."""
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing refresh token cookie")

    try:
        payload = verify_token(raw_token)
    except ValueError:
        log.warning("token_refresh_failed", reason="invalid_or_expired")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")  # noqa: B904

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Revoke the old refresh token (rotation)
    revoked_ok = revoke_token(raw_token)
    if not revoked_ok:
        log.error("token_revocation_failed", user_id=user_id)
        raise HTTPException(
            status_code=503,
            detail="Token revocation service unavailable — refresh rejected for safety",
        )

    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    response = JSONResponse(content={"status": "ok"})
    _set_token_cookies(response, new_access, new_refresh)
    return response


@router.post("/auth/logout", status_code=204)
def logout(request: Request, user: User = Depends(require_auth)) -> Response:
    """Invalidate the current session (revoke tokens)."""
    access_token = request.cookies.get("access_token")
    refresh_token = request.cookies.get("refresh_token")
    if access_token:
        revoke_token(access_token)
    if refresh_token:
        revoke_token(refresh_token)
    log.info("user_logged_out", user_id=user.id)
    response = Response(status_code=204)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie("token_expires_at", path="/")
    return response


@router.get("/auth/me", response_model=User)
def me(user: User = Depends(require_auth)) -> User:
    """Return the current authenticated user."""
    return user
