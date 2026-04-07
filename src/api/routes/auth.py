"""Authentication endpoints for OAuth login flows."""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from src.api.middleware import require_auth
from src.auth.models import AuthorizationUrlResponse, Role, TokenResponse, User
from src.auth.providers import (
    PROVIDERS,
    OAuthUserInfo,
    get_provider,
    retrieve_pkce_verifier,
    store_pkce_verifier,
)
from src.auth.tokens import (
    create_access_token,
    create_refresh_token,
    revoke_all_user_tokens,
    revoke_token,
    verify_token,
)
from src.config import get_settings

log = structlog.get_logger(logger_name=__name__)

router = APIRouter()


@router.get("/auth/providers")
def list_providers() -> list[str]:
    """Return names of OAuth providers that have credentials configured."""
    settings = get_settings().auth
    credential_fields = {
        "google": (settings.google_client_id, settings.google_client_secret),
        "github": (settings.github_client_id, settings.github_client_secret),
        "apple": (settings.apple_client_id, settings.apple_client_secret),
        "facebook": (settings.facebook_client_id, settings.facebook_client_secret),
    }
    return [
        name
        for name, (client_id, client_secret) in credential_fields.items()
        if client_id and client_secret
    ]


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


def _upsert_user(request: Request, user_id: str, user_info: OAuthUserInfo) -> str:
    """Create or update the USER node in Neo4j. Returns the user's role.

    When ``AUTH_FIRST_USER_IS_ADMIN`` is ``true`` and no USER nodes exist yet,
    the newly created user is automatically promoted to admin.
    New users receive the ``viewer`` role by default.
    """
    try:
        neo4j = request.app.state.neo4j
    except AttributeError:
        log.debug("neo4j_not_available_for_upsert", user_id=user_id)
        return Role.VIEWER

    settings = get_settings()

    # Determine whether this user should be auto-promoted
    make_admin = False
    default_role = Role.VIEWER
    if settings.auth.first_user_is_admin:
        count_result = neo4j.execute_read("MATCH (u:USER) RETURN count(u) AS cnt")
        user_count = count_result[0]["cnt"] if count_result else 0
        if user_count == 0:
            make_admin = True
            default_role = Role.ADMIN
            log.info("first_user_auto_admin", user_id=user_id)

    query = """
        MERGE (u:USER {id: $user_id})
        ON CREATE SET
            u.email = $email,
            u.name = $name,
            u.provider = $provider,
            u.created_at = datetime(),
            u.is_admin = $is_admin,
            u.is_suspended = false,
            u.role = $default_role
        ON MATCH SET
            u.email = $email,
            u.name = $name
        RETURN u
    """
    records = neo4j.execute_write(
        query,
        {
            "user_id": user_id,
            "email": user_info.email,
            "name": user_info.name,
            "provider": user_info.provider,
            "is_admin": make_admin,
            "default_role": default_role.value,
        },
    )

    if records:
        role: str = records[0]["u"].get("role", Role.VIEWER)
        return role
    return default_role.value


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
    user_role = _upsert_user(request, user_id, user_info)

    access_token = create_access_token(user_id, role=user_role)
    refresh_token = create_refresh_token(user_id)

    # Redirect to frontend callback page with token
    params = urlencode({"token": access_token, "refresh_token": refresh_token})
    return RedirectResponse(url=f"/auth/callback/{provider}?{params}", status_code=302)


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(request: Request) -> TokenResponse:
    """Refresh an access token using a refresh token.

    Accepts the refresh token from an httpOnly cookie or Authorization header.
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            refresh_token = auth_header[7:]
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    try:
        payload = verify_token(refresh_token)
    except ValueError as exc:
        # Token reuse detection: if a revoked refresh token is presented,
        # it indicates the token family has been compromised. Revoke all
        # tokens for the user as a safety measure.
        if "revoked" in str(exc):
            from jose import jwt as jose_jwt

            try:
                settings = get_settings().auth
                raw = jose_jwt.decode(
                    refresh_token,
                    settings.jwt_secret,
                    algorithms=[settings.jwt_algorithm],
                    options={"verify_exp": False},
                )
                compromised_user = raw.get("sub")
                if isinstance(compromised_user, str):
                    log.warning("token_reuse_detected", user_id=compromised_user)
                    revoke_all_user_tokens(compromised_user)
            except Exception:  # noqa: BLE001
                pass
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")  # noqa: B904

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Revoke the old refresh token (rotation)
    revoke_token(refresh_token)

    # Look up current role from Neo4j so the new access token is up-to-date
    user_role: str = Role.VIEWER
    try:
        neo4j = request.app.state.neo4j
        records = neo4j.execute_read(
            "MATCH (u:USER {id: $user_id}) RETURN u.role AS role", {"user_id": user_id}
        )
        if records and records[0].get("role"):
            user_role = records[0]["role"]
    except Exception:  # noqa: BLE001
        log.debug("neo4j_role_lookup_failed_on_refresh", user_id=user_id)

    settings = get_settings().auth
    new_access = create_access_token(user_id, role=user_role)
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


@router.post("/auth/logout-all", status_code=204)
def logout_all(user: User = Depends(require_auth)) -> None:
    """Invalidate all sessions for the current user across all devices."""
    revoke_all_user_tokens(user.id)
    log.info("logout_all_devices", user_id=user.id)
    return None


@router.get("/auth/me", response_model=User)
def me(user: User = Depends(require_auth)) -> User:
    """Return the current authenticated user."""
    return user
