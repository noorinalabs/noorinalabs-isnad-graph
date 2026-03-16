"""Admin API routes package."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.routes.admin.analytics import router as analytics_router
from src.api.routes.admin.health import router as health_router
from src.api.routes.admin.stats import router as stats_router
from src.api.routes.admin.users import router as users_router

router = APIRouter()
router.include_router(users_router)
router.include_router(health_router)
router.include_router(stats_router)
router.include_router(analytics_router)
