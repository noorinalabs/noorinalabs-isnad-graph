"""Authentication endpoints for OAuth login flows."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import RedirectResponse, Response

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


def _set_token_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set httpOnly cookie pair on a response."""
    settings = get_settings().auth
    common: dict[str, object] = {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "path": "/",
    }
    if settings.cookie_domain:
        common["domain"] = settings.cookie_domain
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **common,  # type: ignore[arg-type]
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.refresh_token_expire_days * 86400,
        **common,  # type: ignore[arg-type]
    )


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


@router.get("/auth/callback/{provider}")
async def callback(provider: str, code: str, state: str) -> RedirectResponse:
    """Handle OAuth callback — upsert user in PG, set httpOnly cookies, redirect."""
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

    # Upsert user in PostgreSQL
    from src.auth.pg_users import ensure_users_table, upsert_user
    from src.utils.pg_client import PgClient

    pg = PgClient()
    try:
        ensure_users_table(pg)
        user = upsert_user(
            pg,
            provider=user_info.provider,
            provider_user_id=user_info.provider_user_id,
            email=user_info.email or None,
            name=user_info.name,
        )
    finally:
        pg.close()

    settings = get_settings().auth
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    redirect_url = settings.frontend_redirect_url.rstrip("/")
    response = RedirectResponse(url=redirect_url, status_code=302)
    _set_token_cookies(response, access_token, refresh_token)
    return response


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest) -> Response:
    """Refresh an access token using a valid refresh token (with rotation).

    Returns new tokens as JSON AND sets updated httpOnly cookies.
    """
    token = body.refresh_token
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = verify_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")  # noqa: B904

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Revoke the old refresh token (rotation)
    revoke_token(token)

    settings = get_settings().auth
    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    token_resp = TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )
    from fastapi.responses import JSONResponse

    response = JSONResponse(content=token_resp.model_dump())
    _set_token_cookies(response, new_access, new_refresh)
    return response


@router.post("/auth/logout", status_code=204)
def logout(user: User = Depends(require_auth)) -> Response:
    """Invalidate the current session — clear auth cookies."""
    response = Response(status_code=204)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response


@router.get("/auth/me", response_model=User)
def me(user: User = Depends(require_auth)) -> User:
    """Return the current authenticated user from PostgreSQL."""
    return user
