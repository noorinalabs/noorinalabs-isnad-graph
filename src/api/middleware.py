"""Authentication and security middleware for FastAPI."""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import structlog
from fastapi import Request
from fastapi.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from src.auth.models import User

if TYPE_CHECKING:
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
        response.headers["X-XSS-Protection"] = "1; mode=block"
        hsts = f"max-age={self._cfg.hsts_max_age}"
        if self._cfg.hsts_include_subdomains:
            hsts += "; includeSubDomains"
        response.headers["Strict-Transport-Security"] = hsts
        response.headers["Content-Security-Policy"] = self._cfg.content_security_policy
        response.headers["Referrer-Policy"] = self._cfg.referrer_policy
        response.headers["Permissions-Policy"] = self._cfg.permissions_policy
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


async def require_admin(request: Request) -> User:
    """Require authenticated user with is_admin=True. Return 403 if not admin."""
    user = await require_auth(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_auth(request: Request) -> User:
    """FastAPI dependency that requires a valid access token.

    Checks for the token in this order:
    1. ``access_token`` httpOnly cookie
    2. ``Authorization: Bearer <token>`` header

    After verifying the JWT, looks up the user in PostgreSQL.
    Raises 401 if the token is missing/invalid or the user is not found.
    Raises 403 if the user is suspended.
    """
    token: str | None = request.cookies.get("access_token")

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ")

    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

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

    from src.auth.pg_users import get_user_by_id
    from src.utils.pg_client import PgClient

    try:
        pg = PgClient()
        try:
            user = get_user_by_id(pg, user_id)
        finally:
            pg.close()
    except Exception:
        raise HTTPException(status_code=401, detail="User lookup failed")  # noqa: B904

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    if user.is_suspended:
        raise HTTPException(status_code=403, detail="Account suspended")

    return user
