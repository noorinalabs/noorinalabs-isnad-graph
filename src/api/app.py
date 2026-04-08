"""FastAPI application for isnad-graph API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    SessionTrackingMiddleware,
    require_admin,
    require_auth,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage Neo4j driver lifecycle."""
    from src.config import get_settings
    from src.utils.neo4j_client import Neo4jClient

    settings = get_settings()
    app.state.neo4j = Neo4jClient(
        uri=settings.neo4j.uri,
        user=settings.neo4j.user,
        password=settings.neo4j.password,
    )
    yield
    app.state.neo4j.close()


OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Health and readiness checks.",
    },
    {
        "name": "auth",
        "description": "OAuth login, token refresh, logout, and user profile.",
    },
    {
        "name": "2fa",
        "description": "Two-factor authentication enrollment and verification.",
    },
    {
        "name": "narrators",
        "description": "Look up narrators, their biographies, chains, and ego-networks.",
    },
    {
        "name": "hadiths",
        "description": "Retrieve individual hadiths and their chain visualizations.",
    },
    {
        "name": "collections",
        "description": "Browse hadith collections (Sunni and Shia).",
    },
    {
        "name": "graph",
        "description": "Raw graph queries — shortest paths, subgraphs, community detection.",
    },
    {
        "name": "search",
        "description": "Full-text and semantic search across narrators and hadiths.",
    },
    {
        "name": "parallels",
        "description": "Cross-collection and cross-sectarian parallel hadith detection.",
    },
    {
        "name": "timeline",
        "description": "Historical timeline data for narrator activity and events.",
    },
    {
        "name": "admin",
        "description": "Admin endpoints: user management, health probes, stats, analytics.",
    },
]

API_DESCRIPTION = """\
# isnad-graph API

Computational hadith analysis platform providing access to a Neo4j-backed graph
of Sunni and Shia hadith collections, narrator networks, and isnad (chain of
narration) analysis.

## Authentication

All endpoints except `/health` and `/api/v1/auth/*` require a valid JWT bearer
token. Obtain one via the OAuth login flow:

1. `POST /api/v1/auth/login/{provider}` — get the provider's authorization URL
2. Browser redirect → provider consent screen → callback
3. `GET /api/v1/auth/callback/{provider}` — exchange code for access + refresh tokens
4. Include `Authorization: Bearer <access_token>` on subsequent requests
5. `POST /api/v1/auth/refresh` — rotate tokens before expiry

Supported providers: **Google**, **Apple**, **Facebook**, **GitHub**.

## Rate Limiting

All endpoints are rate-limited to **120 requests/minute** per client IP.
Exceeding the limit returns `429 Too Many Requests` with a `Retry-After` header.

## Error Format

```json
{"detail": "Human-readable error message"}
```

Standard HTTP status codes: `400` bad request, `401` unauthorized,
`404` not found, `413` body too large, `429` rate limited, `500` server error.
"""


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from src.config import get_settings

    settings = get_settings()
    app = FastAPI(
        title="isnad-graph API",
        description=API_DESCRIPTION,
        version="0.1.0",
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SessionTrackingMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_body_size=1_048_576)
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.rate_limit.requests_per_minute,
        window_seconds=settings.rate_limit.window_seconds,
        redis_url=settings.redis.url,
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID", "X-CSRF-Token"],
    )
    from src.api.routes import (
        auth,
        collections,
        graph,
        hadiths,
        health,
        narrators,
        parallels,
        search,
        timeline,
    )

    # Public routes — no auth required
    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/api/v1", tags=["auth"])

    # Protected routes — require valid Bearer token
    app.include_router(
        narrators.router,
        prefix="/api/v1",
        tags=["narrators"],
        dependencies=[Depends(require_auth)],
    )
    app.include_router(
        hadiths.router,
        prefix="/api/v1",
        tags=["hadiths"],
        dependencies=[Depends(require_auth)],
    )
    app.include_router(
        collections.router,
        prefix="/api/v1",
        tags=["collections"],
        dependencies=[Depends(require_auth)],
    )
    app.include_router(
        graph.router,
        prefix="/api/v1",
        tags=["graph"],
        dependencies=[Depends(require_auth)],
    )
    app.include_router(
        search.router,
        prefix="/api/v1",
        tags=["search"],
        dependencies=[Depends(require_auth)],
    )
    app.include_router(
        parallels.router,
        prefix="/api/v1",
        tags=["parallels"],
        dependencies=[Depends(require_auth)],
    )
    app.include_router(
        timeline.router,
        prefix="/api/v1",
        tags=["timeline"],
        dependencies=[Depends(require_auth)],
    )

    from src.api.routes.profile import router as profile_router

    app.include_router(
        profile_router,
        prefix="/api/v1",
        tags=["auth"],
        dependencies=[Depends(require_auth)],
    )

    from src.api.routes.admin import router as admin_router

    app.include_router(
        admin_router,
        prefix="/api/v1/admin",
        tags=["admin"],
        dependencies=[Depends(require_admin)],
    )

    from src.auth.twofa import router as twofa_router

    app.include_router(twofa_router, tags=["2fa"])

    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics"],
    ).instrument(app).expose(app, include_in_schema=False)

    return app
