"""Admin usage analytics endpoint."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from src.api.models import UsageAnalyticsResponse

router = APIRouter()

TimeRange = Literal["1h", "24h", "7d", "30d"]


@router.get("/analytics", response_model=UsageAnalyticsResponse)
def usage_analytics(
    time_range: TimeRange = Query("24h", alias="time_range"),
) -> UsageAnalyticsResponse:
    """Return usage analytics: search volume, popular narrators, API call count.

    Accepts a ``time_range`` query parameter (1h, 24h, 7d, 30d) to control the
    lookback window.  In a production system these would come from a metrics
    store (e.g. Prometheus, Redis counters, or a PostgreSQL analytics table).
    For now we return placeholder zeros — the frontend renders gracefully.
    """
    return UsageAnalyticsResponse(
        search_volume=0,
        api_call_count=0,
        popular_narrators=[],
    )
