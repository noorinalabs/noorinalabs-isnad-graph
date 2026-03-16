"""FastAPI application for isnad-graph API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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
    app = FastAPI(
        title="isnad-graph API",
        description="Computational Hadith Analysis Platform",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # frontend dev server only
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    from src.api.routes import (
        collections,
        graph,
        hadiths,
        health,
        narrators,
        parallels,
        search,
        timeline,
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(narrators.router, prefix="/api/v1", tags=["narrators"])
    app.include_router(hadiths.router, prefix="/api/v1", tags=["hadiths"])
    app.include_router(collections.router, prefix="/api/v1", tags=["collections"])
    app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(parallels.router, prefix="/api/v1", tags=["parallels"])
    app.include_router(timeline.router, prefix="/api/v1", tags=["timeline"])
    return app
