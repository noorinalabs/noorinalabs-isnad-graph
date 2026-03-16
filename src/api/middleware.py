"""Authentication and security middleware for FastAPI."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Request
from fastapi.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from src.auth.models import User

# Default maximum request body size: 1 MB.
DEFAULT_MAX_BODY_SIZE = 1_048_576


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to all responses.

    Header values are read from ``SecurityHeaderSettings`` so they can be
    overridden per environment (e.g. relaxed CSP for development).
    """

    def __init__(self, app: object, settings: object | None = None) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        from src.config import SecurityHeaderSettings, get_settings

        if settings is not None:
            self._cfg: SecurityHeaderSettings = settings  # type: ignore[assignment]
        else:
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
    """Simple in-memory rate limiter using a sliding window per client IP.

    This is suitable for single-process deployments. For multi-process or
    distributed deployments, use Redis-backed rate limiting instead.
    """

    def __init__(
        self,
        app: object,
        requests_per_minute: int = 60,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.requests_per_minute = requests_per_minute
        self._window: dict[str, list[float]] = {}

    async def dispatch(
        self, request: StarletteRequest, call_next: RequestResponseEndpoint
    ) -> Response:
        import time

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - 60.0

        # Get or create the request log for this IP
        timestamps = self._window.get(client_ip, [])
        # Prune old entries outside the window
        timestamps = [t for t in timestamps if t > window_start]

        if len(timestamps) >= self.requests_per_minute:
            return Response(
                status_code=429,
                content="Rate limit exceeded. Try again later.",
                headers={"Retry-After": "60"},
            )

        timestamps.append(now)
        self._window[client_ip] = timestamps
        return await call_next(request)


async def require_admin(request: Request) -> User:
    """Require authenticated user with is_admin=True. Return 403 if not admin."""
    user = await require_auth(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_auth(request: Request) -> User:
    """FastAPI dependency that requires a valid Bearer token.

    Extracts the JWT from the Authorization header, verifies it,
    and returns a User object. Raises 401 if the token is missing or invalid.
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

    return User(
        id=user_id,
        email=f"{user_id}@placeholder",
        name=user_id,
        provider="jwt",
        provider_user_id=user_id,
        created_at=datetime.now(UTC),
    )
