"""Admin dashboard stats endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from src.api.deps import get_neo4j
from src.utils.neo4j_client import Neo4jClient

router = APIRouter(prefix="/dashboard")


class RoleCount(BaseModel):
    """User count for a specific role."""

    model_config = ConfigDict(frozen=True)

    role: str
    count: int


class DashboardStats(BaseModel):
    """Admin dashboard aggregate statistics."""

    model_config = ConfigDict(frozen=True)

    total_users: int
    active_users: int
    suspended_users: int
    users_by_role: list[RoleCount]
    new_registrations_7d: int
    active_sessions: int


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> DashboardStats:
    """Return aggregate user and session statistics."""
    total_query = "MATCH (u:USER) RETURN count(u) AS total"
    total_result = neo4j.execute_read(total_query, {})
    total_users = total_result[0]["total"] if total_result else 0

    active_query = (
        "MATCH (u:USER) WHERE u.is_suspended IS NULL OR u.is_suspended = false "
        "RETURN count(u) AS active"
    )
    active_result = neo4j.execute_read(active_query, {})
    active_users = active_result[0]["active"] if active_result else 0

    suspended_query = "MATCH (u:USER) WHERE u.is_suspended = true RETURN count(u) AS suspended"
    suspended_result = neo4j.execute_read(suspended_query, {})
    suspended_users = suspended_result[0]["suspended"] if suspended_result else 0

    role_query = """
        MATCH (u:USER)
        RETURN coalesce(u.role, 'viewer') AS role, count(u) AS cnt
        ORDER BY cnt DESC
    """
    role_records = neo4j.execute_read(role_query, {})
    users_by_role = [RoleCount(role=r["role"], count=r["cnt"]) for r in role_records]

    new_query = """
        MATCH (u:USER)
        WHERE u.created_at >= datetime() - duration('P7D')
        RETURN count(u) AS new_count
    """
    new_result = neo4j.execute_read(new_query, {})
    new_registrations = new_result[0]["new_count"] if new_result else 0

    session_query = """
        MATCH (s:SESSION)
        WHERE s.revoked IS NULL OR s.revoked = false
        RETURN count(s) AS active_sessions
    """
    session_result = neo4j.execute_read(session_query, {})
    active_sessions = session_result[0]["active_sessions"] if session_result else 0

    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        suspended_users=suspended_users,
        users_by_role=users_by_role,
        new_registrations_7d=new_registrations,
        active_sessions=active_sessions,
    )
