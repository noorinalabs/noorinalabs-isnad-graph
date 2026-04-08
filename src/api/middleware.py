"""Authentication and security middleware for FastAPI."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from fastapi import Request
from fastapi.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from src.auth.models import ROLE_HIERARCHY, Role, User

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.config import SecurityHeaderSettings

# Default maximum request body size: 1 MB.
DEFAULT_MAX_BODY_SIZE = 1_048_576

log = structlog.get_logger(logger_name=__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to all responses.

    Header values are read from ``SecurityHeaderSettings`` so they can be
    overridden per environment (e.g. relaxed CSP for development).
    """

    def __init__(self, app: object, settings: SecurityHeaderSettings | None = None) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        if settings is not None:
            self._cfg = settings
        else:
            from src.config import get_settings

            self._cfg = get_settings().security_headers

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = self._cfg.x_frame_options
        response.headers["X-XSS-Protection"] = self._cfg.x_xss_protection
        hsts = f"max-age={self._cfg.hsts_max_age}"
        if self._cfg.hsts_include_subdomains:
            hsts += "; includeSubDomains"
        if self._cfg.hsts_preload:
            hsts += "; preload"
        response.headers["Strict-Transport-Security"] = hsts
        response.headers["Content-Security-Policy"] = self._cfg.content_security_policy
        response.headers["Referrer-Policy"] = self._cfg.referrer_policy
        response.headers["Permissions-Policy"] = self._cfg.permissions_policy
        response.headers["Cross-Origin-Opener-Policy"] = self._cfg.cross_origin_opener_policy
        response.headers["Cross-Origin-Resource-Policy"] = self._cfg.cross_origin_resource_policy
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with bodies exceeding a configurable size limit."""

    def __init__(self, app: object, max_body_size: int = DEFAULT_MAX_BODY_SIZE) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.max_body_size = max_body_size

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                return Response(status_code=400, content="Invalid Content-Length header")
            if length > self.max_body_size:
                return Response(
                    status_code=413,
                    content=f"Request body too large. Maximum size: {self.max_body_size} bytes",
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter with Redis backend and in-memory fallback.

    In production (multi-worker), uses a Redis sorted set per client IP so
    that rate limit state is shared across all uvicorn workers. Falls back
    to a per-process in-memory window when Redis is unavailable.
    """

    def __init__(
        self,
        app: object,
        requests_per_minute: int = 60,
        window_seconds: int = 60,
        redis_url: str | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self._redis_url = redis_url
        self._redis: object | None = None
        self._redis_checked = False
        # In-memory fallback
        self._window: dict[str, list[float]] = {}

    def _get_redis(self) -> object | None:
        """Lazily connect to Redis. Returns None if unavailable."""
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        url = self._redis_url
        if url is None:
            try:
                from src.config import get_settings

                url = get_settings().redis.url
            except Exception:  # noqa: BLE001
                return None
        try:
            import redis as redis_lib

            client = redis_lib.Redis.from_url(url, decode_responses=True)
            client.ping()
            self._redis = client
        except Exception:  # noqa: BLE001
            self._redis = None
        return self._redis

    def _check_redis(self, client_ip: str, now: float) -> bool | None:
        """Check rate limit via Redis. Returns True if allowed, False if
        exceeded, or None if Redis is unavailable."""
        redis_client = self._get_redis()
        if redis_client is None:
            return None
        try:
            import redis as redis_lib

            client: redis_lib.Redis = redis_client  # type: ignore[assignment]
            key = f"ratelimit:{client_ip}"
            window_start = now - self.window_seconds
            pipe = client.pipeline()
            # Remove entries outside the sliding window
            pipe.zremrangebyscore(key, "-inf", window_start)
            # Count remaining entries in the window
            pipe.zcard(key)
            # Add the current request timestamp
            pipe.zadd(key, {str(now): now})
            # Set expiry so keys don't linger forever
            pipe.expire(key, self.window_seconds + 1)
            results = pipe.execute()
            count: int = results[1]
            return count < self.requests_per_minute
        except (redis_lib.RedisError, OSError):  # fmt: skip
            # Redis went away mid-request — fall back to in-memory
            self._redis = None
            self._redis_checked = False
            return None

    def _check_memory(self, client_ip: str, now: float) -> bool:
        """Check rate limit using in-memory sliding window."""
        window_start = now - float(self.window_seconds)
        timestamps = self._window.get(client_ip, [])
        timestamps = [t for t in timestamps if t > window_start]
        if len(timestamps) >= self.requests_per_minute:
            self._window[client_ip] = timestamps
            return False
        timestamps.append(now)
        self._window[client_ip] = timestamps
        return True

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        allowed = self._check_redis(client_ip, now)
        if allowed is None:
            allowed = self._check_memory(client_ip, now)

        if not allowed:
            return Response(
                status_code=429,
                content="Rate limit exceeded. Try again later.",
                headers={"Retry-After": str(self.window_seconds)},
            )
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assign a unique request ID to every request and log request lifecycle.

    The request ID is:
    - stored in structlog contextvars so all logs within the request include it
    - returned in the ``X-Request-ID`` response header for client-side tracing

    If the caller supplies an ``X-Request-ID`` header it is respected (truncated
    to 64 chars); otherwise a new UUID4 is generated.
    """

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = (request.headers.get("X-Request-ID") or uuid.uuid4().hex)[:64]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
        )

        start = time.monotonic()
        log.info("request_started")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            log.exception("request_failed", duration_ms=duration_ms)
            raise

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        log.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.clear_contextvars()
        return response


class SessionTrackingMiddleware(BaseHTTPMiddleware):
    """Validate server-side sessions and enforce idle timeout.

    On each authenticated request, checks that the session is still active
    and refreshes its last_active timestamp. Returns 401 with an
    ``X-Session-Idle-Timeout`` header if the session has expired, and
    includes ``X-Session-Warning-Seconds`` when the session is approaching
    its idle timeout so the frontend can display a warning.
    """

    _EXEMPT_PREFIXES = (
        "/api/v1/auth/",
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
    )

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        if not path.startswith("/api/") or any(path.startswith(p) for p in self._EXEMPT_PREFIXES):
            return await call_next(request)

        session_id = request.headers.get("X-Session-ID")
        if not session_id:
            return await call_next(request)

        from src.auth.sessions import get_idle_timeout_warning_seconds, get_session, touch_session

        session = get_session(session_id)
        if session is None:
            import json

            return Response(
                status_code=401,
                content=json.dumps(
                    {
                        "detail": "Session has expired due to inactivity.",
                        "code": "session_idle_timeout",
                    }
                ),
                media_type="application/json",
                headers={"X-Session-Idle-Timeout": "true"},
            )

        touch_session(session_id)

        response = await call_next(request)

        # Add warning header if session is approaching idle timeout
        from src.config import get_settings

        settings = get_settings().auth
        idle_timeout = settings.session_idle_timeout_minutes * 60
        elapsed = time.time() - session.last_active
        remaining = idle_timeout - elapsed
        warning_threshold = get_idle_timeout_warning_seconds()
        if remaining <= warning_threshold:
            response.headers["X-Session-Warning-Seconds"] = str(int(remaining))

        return response


def require_role(min_role: Role) -> Callable[..., object]:
    """Return a FastAPI dependency that enforces a minimum role level.

    The user's role is resolved from the DB record (via ``require_auth``).
    Users without a role default to ``Role.VIEWER``.
    """

    async def dependency(request: Request) -> User:
        user = await require_auth(request)
        user_role = Role(user.role) if user.role else Role.VIEWER
        if ROLE_HIERARCHY.get(user_role, 0) < ROLE_HIERARCHY[min_role]:
            raise HTTPException(
                status_code=403,
                detail=f"Requires {min_role.value} role or higher",
            )
        return user

    return dependency


async def require_admin(request: Request) -> User:
    """Require authenticated user with admin role. Return 403 if not admin.

    Delegates to ``require_role(Role.ADMIN)`` for role-based checks, and also
    honours the legacy ``is_admin`` boolean for backward compatibility.
    """
    user = await require_auth(request)

    # Validate role string against known Role enum values (#483)
    if user.role is not None:
        role_values = {r.value for r in Role}
        if user.role not in role_values:
            log.warning(
                "unknown_role_string",
                user_id=user.id,
                role=user.role,
                msg="User has role string not in Role enum; defaulting to viewer-level access",
            )

    # Accept either legacy is_admin flag or role-based admin
    user_role = Role(user.role) if user.role in {r.value for r in Role} else Role.VIEWER
    is_role_admin = ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY[Role.ADMIN]

    if not user.is_admin and not is_role_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_auth(request: Request) -> User:
    """FastAPI dependency that requires a valid Bearer token.

    Extracts the JWT from the Authorization header, verifies it, and returns
    a User object. When possible, looks up the real user record from Neo4j
    so that email/name are not placeholder values (#482).

    Raises 401 if the token is missing or invalid.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ")

    from src.auth.tokens import verify_token

    try:
        payload = verify_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")  # noqa: B904

    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Attempt to look up the real user record from Neo4j (#482)
    try:
        neo4j = request.app.state.neo4j
        records = neo4j.execute_read("MATCH (u:USER {id: $user_id}) RETURN u", {"user_id": user_id})
        if records:
            u = records[0]["u"]
            return User(
                id=user_id,
                email=u.get("email", user_id),
                name=u.get("name", user_id),
                provider=u.get("provider", "jwt"),
                provider_user_id=user_id,
                created_at=datetime.now(UTC),
                is_admin=u.get("is_admin", False),
                role=u.get("role"),
            )
    except Exception:  # noqa: BLE001
        log.debug("neo4j_user_lookup_failed", user_id=user_id)

    # Fall back to JWT claims when Neo4j is unavailable
    token_role = payload.get("role")
    return User(
        id=user_id,
        email=user_id,
        name=user_id,
        provider="jwt",
        provider_user_id=user_id,
        created_at=datetime.now(UTC),
        role=token_role if isinstance(token_role, str) else None,
    )
