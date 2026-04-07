"""Admin API routes package."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.routes.admin.analytics import router as analytics_router
from src.api.routes.admin.audit import router as audit_router
from src.api.routes.admin.config import router as config_router
from src.api.routes.admin.dashboard import router as dashboard_router
from src.api.routes.admin.health import router as health_router
from src.api.routes.admin.moderation import router as moderation_router
from src.api.routes.admin.reports import router as reports_router
from src.api.routes.admin.stats import router as stats_router
from src.api.routes.admin.users import router as users_router

router = APIRouter()
router.include_router(users_router)
router.include_router(health_router)
router.include_router(stats_router)
router.include_router(analytics_router)
router.include_router(moderation_router)
router.include_router(reports_router)
router.include_router(config_router)
router.include_router(audit_router)
router.include_router(dashboard_router)
