"""Admin user management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from src.api.deps import get_neo4j
from src.api.models import PaginatedResponse, UserAdminResponse, UserUpdateRequest
from src.auth.models import Role
from src.utils.neo4j_client import Neo4jClient

router = APIRouter(prefix="/users")


@router.get("", response_model=PaginatedResponse[UserAdminResponse])
def list_users(
    neo4j: Neo4jClient = Depends(get_neo4j),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    role: str | None = Query(None),
) -> PaginatedResponse[UserAdminResponse]:
    """List users with optional search and role filters."""
    params: dict[str, object] = {"skip": (page - 1) * limit, "limit": limit}
    where_clauses: list[str] = []

    if search:
        where_clauses.append("(u.name CONTAINS $search OR u.email CONTAINS $search)")
        params["search"] = search
    if role:
        where_clauses.append("u.role = $role")
        params["role"] = role

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_query = f"MATCH (u:USER) {where} RETURN count(u) AS total"
    count_result = neo4j.execute_read(count_query, params)
    total = count_result[0]["total"] if count_result else 0

    query = f"""
        MATCH (u:USER) {where}
        RETURN u ORDER BY u.created_at DESC
        SKIP $skip LIMIT $limit
    """
    records = neo4j.execute_read(query, params)

    items = [
        UserAdminResponse(
            id=r["u"]["id"],
            email=r["u"].get("email", ""),
            name=r["u"].get("name", ""),
            provider=r["u"].get("provider", ""),
            is_admin=r["u"].get("is_admin", False),
            is_suspended=r["u"].get("is_suspended", False),
            created_at=r["u"].get("created_at", ""),
            role=r["u"].get("role"),
        )
        for r in records
    ]

    return PaginatedResponse[UserAdminResponse](items=items, total=total, page=page, limit=limit)


@router.get("/{user_id}", response_model=UserAdminResponse)
def get_user(
    user_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> UserAdminResponse:
    """Get a single user by ID."""
    query = "MATCH (u:USER {id: $user_id}) RETURN u"
    records = neo4j.execute_read(query, {"user_id": user_id})

    if not records:
        raise HTTPException(status_code=404, detail="User not found")

    r = records[0]
    return UserAdminResponse(
        id=r["u"]["id"],
        email=r["u"].get("email", ""),
        name=r["u"].get("name", ""),
        provider=r["u"].get("provider", ""),
        is_admin=r["u"].get("is_admin", False),
        is_suspended=r["u"].get("is_suspended", False),
        created_at=r["u"].get("created_at", ""),
        role=r["u"].get("role"),
    )


@router.patch("/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: str,
    body: UserUpdateRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> UserAdminResponse:
    """Update user properties (suspend, promote, change role)."""
    set_clauses: list[str] = []
    params: dict[str, object] = {"user_id": user_id}

    if body.is_admin is not None:
        set_clauses.append("u.is_admin = $is_admin")
        params["is_admin"] = body.is_admin
    if body.is_suspended is not None:
        set_clauses.append("u.is_suspended = $is_suspended")
        params["is_suspended"] = body.is_suspended
    if body.role is not None:
        role_values = {r.value for r in Role}
        if body.role not in role_values:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
        set_clauses.append("u.role = $role")
        params["role"] = body.role

    if not set_clauses:
        raise HTTPException(status_code=400, detail="No fields to update")

    query = f"""
        MATCH (u:USER {{id: $user_id}})
        SET {", ".join(set_clauses)}
        RETURN u
    """
    records = neo4j.execute_write(query, params)

    if not records:
        raise HTTPException(status_code=404, detail="User not found")

    r = records[0]
    return UserAdminResponse(
        id=r["u"]["id"],
        email=r["u"].get("email", ""),
        name=r["u"].get("name", ""),
        provider=r["u"].get("provider", ""),
        is_admin=r["u"].get("is_admin", False),
        is_suspended=r["u"].get("is_suspended", False),
        created_at=r["u"].get("created_at", ""),
        role=r["u"].get("role"),
    )


class RoleUpdateRequest(BaseModel):
    """Request body for changing a user's role."""

    model_config = ConfigDict(frozen=True)

    role: str


@router.patch("/{user_id}/role", response_model=UserAdminResponse)
def update_user_role(
    user_id: str,
    body: RoleUpdateRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> UserAdminResponse:
    """Change a user's role (admin only)."""
    role_values = {r.value for r in Role}
    if body.role not in role_values:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    # Sync is_admin flag with role for backward compatibility
    is_admin = body.role == Role.ADMIN

    query = """
        MATCH (u:USER {id: $user_id})
        SET u.role = $role, u.is_admin = $is_admin
        RETURN u
    """
    records = neo4j.execute_write(
        query, {"user_id": user_id, "role": body.role, "is_admin": is_admin}
    )

    if not records:
        raise HTTPException(status_code=404, detail="User not found")

    # Invalidate all sessions and tokens when role changes (#728)
    from src.auth.sessions import destroy_all_user_sessions
    from src.auth.tokens import revoke_all_user_tokens

    revoke_all_user_tokens(user_id)
    destroy_all_user_sessions(user_id)

    r = records[0]
    return UserAdminResponse(
        id=r["u"]["id"],
        email=r["u"].get("email", ""),
        name=r["u"].get("name", ""),
        provider=r["u"].get("provider", ""),
        is_admin=r["u"].get("is_admin", False),
        is_suspended=r["u"].get("is_suspended", False),
        created_at=r["u"].get("created_at", ""),
        role=r["u"].get("role"),
    )
