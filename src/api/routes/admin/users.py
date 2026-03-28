"""Admin user management endpoints — PostgreSQL backed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_pg
from src.api.models import PaginatedResponse, UserAdminResponse, UserUpdateRequest
from src.auth import pg_users
from src.utils.pg_client import PgClient

router = APIRouter(prefix="/users")


@router.get("", response_model=PaginatedResponse[UserAdminResponse])
def list_users(
    pg: PgClient = Depends(get_pg),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    role: str | None = Query(None),
) -> PaginatedResponse[UserAdminResponse]:
    """List users with optional search and role filters."""
    users, total = pg_users.list_users(pg, page=page, limit=limit, search=search, role=role)
    items = [
        UserAdminResponse(
            id=u.id,
            email=u.email or "",
            name=u.name,
            provider=u.provider,
            is_admin=u.is_admin,
            is_suspended=u.is_suspended,
            created_at=u.created_at.isoformat() if u.created_at else "",
            role=u.role,
        )
        for u in users
    ]
    return PaginatedResponse[UserAdminResponse](items=items, total=total, page=page, limit=limit)


@router.get("/{user_id}", response_model=UserAdminResponse)
def get_user(
    user_id: str,
    pg: PgClient = Depends(get_pg),
) -> UserAdminResponse:
    """Get a single user by ID."""
    user = pg_users.get_user_by_id(pg, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserAdminResponse(
        id=user.id,
        email=user.email or "",
        name=user.name,
        provider=user.provider,
        is_admin=user.is_admin,
        is_suspended=user.is_suspended,
        created_at=user.created_at.isoformat() if user.created_at else "",
        role=user.role,
    )


@router.patch("/{user_id}", response_model=UserAdminResponse)
def update_user(
    user_id: str,
    body: UserUpdateRequest,
    pg: PgClient = Depends(get_pg),
) -> UserAdminResponse:
    """Update user properties (suspend, promote, change role)."""
    if body.is_admin is None and body.is_suspended is None and body.role is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    user = pg_users.update_user(
        pg,
        user_id,
        is_admin=body.is_admin,
        is_suspended=body.is_suspended,
        role=body.role,
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserAdminResponse(
        id=user.id,
        email=user.email or "",
        name=user.name,
        provider=user.provider,
        is_admin=user.is_admin,
        is_suspended=user.is_suspended,
        created_at=user.created_at.isoformat() if user.created_at else "",
        role=user.role,
    )
