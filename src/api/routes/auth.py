"""Authentication endpoints for OAuth login flows."""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from src.api.middleware import require_auth
from src.auth.models import AuthorizationUrlResponse, TokenResponse, User
from src.auth.providers import (
    PROVIDERS,
    OAuthUserInfo,
    get_provider,
    retrieve_pkce_verifier,
    store_pkce_verifier,
)
from src.auth.tokens import create_access_token, create_refresh_token, revoke_token, verify_token
from src.config import get_settings

log = structlog.get_logger(logger_name=__name__)

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


def _upsert_user(request: Request, user_id: str, user_info: OAuthUserInfo) -> None:
    """Create or update the USER node in Neo4j.

    When ``AUTH_FIRST_USER_IS_ADMIN`` is ``true`` and no USER nodes exist yet,
    the newly created user is automatically promoted to admin.
    """
    try:
        neo4j = request.app.state.neo4j
    except AttributeError:
        log.debug("neo4j_not_available_for_upsert", user_id=user_id)
        return

    settings = get_settings()

    # Determine whether this user should be auto-promoted
    make_admin = False
    if settings.auth.first_user_is_admin:
        count_result = neo4j.execute_read("MATCH (u:USER) RETURN count(u) AS cnt")
        user_count = count_result[0]["cnt"] if count_result else 0
        if user_count == 0:
            make_admin = True
            log.info("first_user_auto_admin", user_id=user_id)

    query = """
        MERGE (u:USER {id: $user_id})
        ON CREATE SET
            u.email = $email,
            u.name = $name,
            u.provider = $provider,
            u.created_at = datetime(),
            u.is_admin = $is_admin,
            u.is_suspended = false
        ON MATCH SET
            u.email = $email,
            u.name = $name
        RETURN u
    """
    neo4j.execute_write(
        query,
        {
            "user_id": user_id,
            "email": user_info.email,
            "name": user_info.name,
            "provider": user_info.provider,
            "is_admin": make_admin,
        },
    )


@router.get("/auth/callback/{provider}")
async def callback(provider: str, code: str, state: str, request: Request) -> RedirectResponse:
    """Handle OAuth callback — exchange code for tokens, upsert user, redirect to frontend."""
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

    # Upsert user in Neo4j and apply first-user-is-admin if configured
    _upsert_user(request, user_id, user_info)

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    # Redirect to frontend callback page with token
    params = urlencode({"token": access_token, "refresh_token": refresh_token})
    return RedirectResponse(url=f"/auth/callback/{provider}?{params}", status_code=302)


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(request: Request) -> TokenResponse:
    """Refresh an access token using the refresh token from httpOnly cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = verify_token(refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")  # noqa: B904

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Revoke the old refresh token (rotation)
    revoke_token(refresh_token)

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
