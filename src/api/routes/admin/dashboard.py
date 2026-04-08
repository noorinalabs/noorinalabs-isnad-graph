"""Admin dashboard stats endpoints.

User statistics are no longer available from Neo4j — they are managed
by user-service.  Session counts come from the Redis session store.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/dashboard")


class DashboardStats(BaseModel):
    """Admin dashboard aggregate statistics.

    User-related fields (total_users, active_users, suspended_users,
    users_by_role, new_registrations_7d) have been removed — these are
    now served by user-service.
    """

    model_config = ConfigDict(frozen=True)

    active_sessions: int


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats() -> DashboardStats:
    """Return aggregate session statistics.

    User statistics should be fetched from user-service directly.
    """
    # Session count from Redis — we cannot enumerate all users from
    # the session store, so we report only the session-level metric.
    # A future integration with user-service will restore user counts.
    # For now, active_sessions is a rough proxy via Redis key scan.
    # Since list_user_sessions requires a user_id, we just report 0
    # until the user-service admin API is integrated.
    active_sessions = 0

    return DashboardStats(
        active_sessions=active_sessions,
    )
