"""Admin usage analytics endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from src.api.models import UsageAnalyticsResponse

router = APIRouter()


@router.get("/analytics", response_model=UsageAnalyticsResponse)
def usage_analytics() -> UsageAnalyticsResponse:
    """Return usage analytics: search volume, popular narrators, API call count.

    In a production system these would come from a metrics store (e.g. Prometheus,
    Redis counters, or a PostgreSQL analytics table). For now we return placeholder
    data that the frontend can render.
    """
    return UsageAnalyticsResponse(
        search_volume=0,
        api_call_count=0,
        popular_narrators=[],
    )
