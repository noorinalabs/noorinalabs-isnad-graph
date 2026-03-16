"""FastAPI application for isnad-graph API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import (
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from src.config import get_settings

    settings = get_settings()
    app = FastAPI(
        title="isnad-graph API",
        description="Computational Hadith Analysis Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_body_size=1_048_576)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
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

    from src.auth.twofa import router as twofa_router

    app.include_router(twofa_router, tags=["2fa"])
    return app
