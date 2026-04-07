"""User profile and session management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from src.api.deps import get_neo4j
from src.api.middleware import require_auth
from src.auth.models import User
from src.utils.neo4j_client import Neo4jClient

router = APIRouter(prefix="/users/me")


class UserPreferences(BaseModel):
    """User preferences stored as properties on the USER node."""

    model_config = ConfigDict(frozen=True)

    default_search_mode: str = "fulltext"
    results_per_page: int = 20
    language_preference: str = "en"
    theme_preference: str = "system"


class UserProfileResponse(BaseModel):
    """Full user profile including preferences."""

    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    name: str
    provider: str
    role: str | None = None
    is_admin: bool = False
    created_at: str
    preferences: UserPreferences


class ProfileUpdateRequest(BaseModel):
    """Request body for updating profile fields."""

    model_config = ConfigDict(frozen=True)

    display_name: str | None = None
    preferences: UserPreferences | None = None


class SessionResponse(BaseModel):
    """An active session entry."""

    model_config = ConfigDict(frozen=True)

    id: str
    created_at: str
    last_active: str
    ip_address: str | None = None
    user_agent: str | None = None
    is_current: bool = False


@router.get("/profile", response_model=UserProfileResponse)
def get_profile(
    user: User = Depends(require_auth),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> UserProfileResponse:
    """Return the full profile for the current user."""
    query = "MATCH (u:USER {id: $user_id}) RETURN u"
    records = neo4j.execute_read(query, {"user_id": user.id})

    if not records:
        raise HTTPException(status_code=404, detail="User not found")

    u = records[0]["u"]
    prefs = UserPreferences(
        default_search_mode=u.get("pref_search_mode", "fulltext"),
        results_per_page=u.get("pref_results_per_page", 20),
        language_preference=u.get("pref_language", "en"),
        theme_preference=u.get("pref_theme", "system"),
    )

    return UserProfileResponse(
        id=u["id"],
        email=u.get("email", ""),
        name=u.get("name", ""),
        provider=u.get("provider", ""),
        role=u.get("role"),
        is_admin=u.get("is_admin", False),
        created_at=str(u.get("created_at", "")),
        preferences=prefs,
    )


@router.patch("/profile", response_model=UserProfileResponse)
def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(require_auth),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> UserProfileResponse:
    """Update the current user's display name and/or preferences."""
    set_clauses: list[str] = []
    params: dict[str, object] = {"user_id": user.id}

    if body.display_name is not None:
        name = body.display_name.strip()
        if not name or len(name) > 200:
            raise HTTPException(status_code=400, detail="Display name must be 1-200 characters")
        set_clauses.append("u.name = $name")
        params["name"] = name

    if body.preferences is not None:
        p = body.preferences
        if p.results_per_page < 5 or p.results_per_page > 100:
            raise HTTPException(status_code=400, detail="Results per page must be 5-100")
        set_clauses.append("u.pref_search_mode = $pref_search_mode")
        set_clauses.append("u.pref_results_per_page = $pref_results_per_page")
        set_clauses.append("u.pref_language = $pref_language")
        set_clauses.append("u.pref_theme = $pref_theme")
        params["pref_search_mode"] = p.default_search_mode
        params["pref_results_per_page"] = p.results_per_page
        params["pref_language"] = p.language_preference
        params["pref_theme"] = p.theme_preference

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

    u = records[0]["u"]
    prefs = UserPreferences(
        default_search_mode=u.get("pref_search_mode", "fulltext"),
        results_per_page=u.get("pref_results_per_page", 20),
        language_preference=u.get("pref_language", "en"),
        theme_preference=u.get("pref_theme", "system"),
    )

    return UserProfileResponse(
        id=u["id"],
        email=u.get("email", ""),
        name=u.get("name", ""),
        provider=u.get("provider", ""),
        role=u.get("role"),
        is_admin=u.get("is_admin", False),
        created_at=str(u.get("created_at", "")),
        preferences=prefs,
    )


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    user: User = Depends(require_auth),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> list[SessionResponse]:
    """List active sessions for the current user."""
    query = """
        MATCH (s:SESSION)-[:BELONGS_TO]->(u:USER {id: $user_id})
        WHERE s.revoked IS NULL OR s.revoked = false
        RETURN s ORDER BY s.created_at DESC
    """
    records = neo4j.execute_read(query, {"user_id": user.id})

    return [
        SessionResponse(
            id=r["s"]["id"],
            created_at=str(r["s"].get("created_at", "")),
            last_active=str(r["s"].get("last_active", r["s"].get("created_at", ""))),
            ip_address=r["s"].get("ip_address"),
            user_agent=r["s"].get("user_agent"),
            is_current=False,
        )
        for r in records
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: str,
    user: User = Depends(require_auth),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> None:
    """Revoke a specific session for the current user."""
    query = """
        MATCH (s:SESSION {id: $session_id})-[:BELONGS_TO]->(u:USER {id: $user_id})
        SET s.revoked = true
        RETURN s
    """
    records = neo4j.execute_write(query, {"session_id": session_id, "user_id": user.id})

    if not records:
        raise HTTPException(status_code=404, detail="Session not found")

    return None
