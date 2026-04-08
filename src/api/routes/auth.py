"""Authentication endpoints for OAuth login flows."""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict

from src.api.middleware import require_auth
from src.auth.models import (
    AuthorizationUrlResponse,
    Role,
    TokenResponse,
    User,
)
from src.auth.providers import (
    PROVIDERS,
    OAuthUserInfo,
    get_provider,
    retrieve_pkce_verifier,
    store_pkce_verifier,
)
from src.auth.sessions import (
    create_session,
    destroy_all_user_sessions,
    destroy_session,
    get_idle_timeout_warning_seconds,
    list_user_sessions,
    touch_session,
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

# CSRF token length (bytes of randomness, hex-encoded to double)
_CSRF_TOKEN_BYTES = 32


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set the refresh token as an httpOnly secure cookie."""
    settings = get_settings().auth
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        path="/api/v1/auth",
        max_age=settings.refresh_token_expire_days * 86400,
    )


def _set_csrf_cookie(response: Response, csrf_token: str) -> None:
    """Set a non-httpOnly CSRF cookie readable by JavaScript."""
    settings = get_settings().auth
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain or None,
        path="/",
        max_age=settings.refresh_token_expire_days * 86400,
    )


def _clear_auth_cookies(response: Response) -> None:
    """Clear refresh token and CSRF cookies."""
    settings = get_settings().auth
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
        domain=settings.cookie_domain or None,
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        domain=settings.cookie_domain or None,
    )


def _verify_csrf(request: Request) -> None:
    """Verify CSRF token: header X-CSRF-Token must match csrf_token cookie.

    This implements the double-submit cookie pattern. The cookie is set
    with SameSite=Lax and is readable by JavaScript. The frontend reads
    the cookie and sends it back in the X-CSRF-Token header. A CSRF
    attacker cannot read the cookie value due to same-origin policy.
    """
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(status_code=403, detail="CSRF validation failed")


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


def _upsert_user(request: Request, user_id: str, user_info: OAuthUserInfo) -> tuple[str, bool]:
    """Create or update the USER node in Neo4j. Returns (role, is_new_user).

    When ``AUTH_FIRST_USER_IS_ADMIN`` is ``true`` and no USER nodes exist yet,
    the newly created user is automatically promoted to admin.
    New users receive the ``viewer`` role by default.
    """
    try:
        neo4j = request.app.state.neo4j
    except AttributeError:
        log.debug("neo4j_not_available_for_upsert", user_id=user_id)
        return Role.VIEWER, True

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
            u.role = $default_role,
            u._created = true
        ON MATCH SET
            u.email = $email,
            u.name = $name,
            u._created = false
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
        node = records[0]["u"]
        role: str = node.get("role", Role.VIEWER)
        is_new = bool(node.get("_created", False))
        # Clean up transient property
        neo4j.execute_write(
            "MATCH (u:USER {id: $user_id}) REMOVE u._created",
            {"user_id": user_id},
        )
        return role, is_new
    return default_role.value, True


@router.get("/auth/callback/{provider}")
async def callback(provider: str, code: str, state: str, request: Request) -> RedirectResponse:
    """Handle OAuth callback — exchange code for tokens, upsert user, redirect to frontend.

    The refresh token is set as an httpOnly cookie (not passed in the URL).
    The access token and metadata are passed via query params to the frontend.
    """
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
        log.warning("oauth_exchange_failed", provider=provider, error=str(exc))
        error_params = urlencode({"error": "oauth_exchange_failed", "provider": provider})
        return RedirectResponse(url=f"/auth/callback/{provider}?{error_params}", status_code=302)

    # Check if user account is suspended
    try:
        neo4j = request.app.state.neo4j
        user_id_check = f"{user_info.provider}:{user_info.provider_user_id}"
        records = neo4j.execute_read(
            "MATCH (u:USER {id: $uid}) RETURN u.is_suspended AS suspended",
            {"uid": user_id_check},
        )
        if records and records[0].get("suspended"):
            error_params = urlencode({"error": "account_suspended", "provider": provider})
            return RedirectResponse(
                url=f"/auth/callback/{provider}?{error_params}", status_code=302
            )
    except Exception:  # noqa: BLE001
        pass

    # Use provider + provider_user_id as the internal user ID
    user_id = f"{user_info.provider}:{user_info.provider_user_id}"

    # Upsert user in Neo4j and apply first-user-is-admin if configured
    user_role, is_new_user = _upsert_user(request, user_id, user_info)

    access_token = create_access_token(user_id, role=user_role)
    refresh_token = create_refresh_token(user_id)
    csrf_token = secrets.token_hex(_CSRF_TOKEN_BYTES)

    # Create a server-side session for tracking
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")
    session_id = create_session(user_id, ip_address, user_agent, role=user_role)

    # Redirect to frontend callback page with access token in URL
    # Refresh token goes in httpOnly cookie — never exposed to JS
    params = urlencode(
        {
            "token": access_token,
            "session_id": session_id,
            "is_new_user": "1" if is_new_user else "0",
        }
    )
    response = RedirectResponse(url=f"/auth/callback/{provider}?{params}", status_code=302)
    _set_refresh_cookie(response, refresh_token)
    _set_csrf_cookie(response, csrf_token)
    return response


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response) -> TokenResponse:
    """Refresh an access token using a refresh token from the httpOnly cookie.

    Requires a valid CSRF token in the X-CSRF-Token header.
    """
    _verify_csrf(request)

    refresh_token = request.cookies.get("refresh_token")
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
        _clear_auth_cookies(response)
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
    new_csrf = secrets.token_hex(_CSRF_TOKEN_BYTES)

    # Set rotated refresh token and CSRF cookie
    _set_refresh_cookie(response, new_refresh)
    _set_csrf_cookie(response, new_csrf)

    return TokenResponse(
        access_token=new_access,
        refresh_token="",
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, user: User = Depends(require_auth)) -> None:
    """Invalidate the current session (revoke tokens, clear cookies, destroy session)."""
    session_id = request.headers.get("X-Session-ID")
    if session_id:
        destroy_session(session_id)
    _clear_auth_cookies(response)
    return None


@router.post("/auth/logout-all", status_code=204)
def logout_all(response: Response, user: User = Depends(require_auth)) -> None:
    """Invalidate all sessions for the current user across all devices."""
    revoke_all_user_tokens(user.id)
    count = destroy_all_user_sessions(user.id)
    _clear_auth_cookies(response)
    log.info("logout_all_devices", user_id=user.id, sessions_destroyed=count)
    return None


@router.get("/auth/me", response_model=User)
def me(user: User = Depends(require_auth)) -> User:
    """Return the current authenticated user."""
    return user


# --- Session management endpoints ---


class SessionResponse(BaseModel):
    """Response model for a single session."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    ip_address: str
    user_agent: str
    created_at: float
    last_active: float


class SessionListResponse(BaseModel):
    """Response model for listing active sessions."""

    model_config = ConfigDict(frozen=True)

    sessions: list[SessionResponse]
    idle_timeout_minutes: int
    warning_seconds: int


@router.get("/auth/sessions", response_model=SessionListResponse)
def list_sessions(user: User = Depends(require_auth)) -> SessionListResponse:
    """List all active sessions for the current user."""
    sessions = list_user_sessions(user.id)
    settings = get_settings().auth
    return SessionListResponse(
        sessions=[
            SessionResponse(
                session_id=s.session_id,
                ip_address=s.ip_address,
                user_agent=s.user_agent,
                created_at=s.created_at,
                last_active=s.last_active,
            )
            for s in sessions
        ],
        idle_timeout_minutes=settings.session_idle_timeout_minutes,
        warning_seconds=get_idle_timeout_warning_seconds(),
    )


@router.delete("/auth/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, user: User = Depends(require_auth)) -> None:
    """Revoke a specific session. Users can only revoke their own sessions."""
    from src.auth.sessions import get_session as get_sess

    session = get_sess(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="Cannot revoke another user's session")
    destroy_session(session_id)
    log.info("session_revoked", user_id=user.id, session_id=session_id)


@router.post("/auth/sessions/heartbeat", status_code=204)
def session_heartbeat(request: Request, user: User = Depends(require_auth)) -> None:
    """Keep the current session alive (reset idle timer)."""
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-ID header")
    alive = touch_session(session_id)
    if not alive:
        raise HTTPException(
            status_code=401,
            detail="Session has expired",
            headers={"X-Session-Idle-Timeout": "true"},
        )
