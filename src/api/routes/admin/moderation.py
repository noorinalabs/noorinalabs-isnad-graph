"""Admin content moderation endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_neo4j
from src.api.models import (
    ModerationFlagRequest,
    ModerationItemResponse,
    ModerationUpdateRequest,
    PaginatedResponse,
)
from src.utils.logging import get_logger
from src.utils.neo4j_client import Neo4jClient

log = get_logger(__name__)

router = APIRouter()


@router.get("/moderation", response_model=PaginatedResponse[ModerationItemResponse])
def list_flagged_content(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="Filter by status: pending, approved, rejected"),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> PaginatedResponse[ModerationItemResponse]:
    """List flagged content items, optionally filtered by status."""
    where = "WHERE m:MODERATION_FLAG"
    params: dict[str, object] = {"skip": (page - 1) * limit, "limit": limit}
    if status is not None:
        where += " AND m.status = $status"
        params["status"] = status

    count_query = f"MATCH (m) {where} RETURN count(m) AS total"
    count_result = neo4j.execute_read(count_query, params)
    total = count_result[0]["total"] if count_result else 0

    query = f"""
        MATCH (m) {where}
        RETURN properties(m) AS props
        ORDER BY m.flagged_at DESC
        SKIP $skip LIMIT $limit
    """
    rows = neo4j.execute_read(query, params)
    items = [ModerationItemResponse(**row["props"]) for row in rows]
    return PaginatedResponse(items=items, total=total, page=page, limit=limit)


@router.patch("/moderation/{item_id}", response_model=ModerationItemResponse)
def update_moderation_item(
    item_id: str,
    body: ModerationUpdateRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> ModerationItemResponse:
    """Approve, reject, or update a flagged content item."""
    now = datetime.now(UTC).isoformat()
    query = """
        MATCH (m:MODERATION_FLAG {id: $id})
        SET m.status = $status,
            m.resolved_at = $resolved_at,
            m.notes = $notes
        RETURN properties(m) AS props
    """
    rows = neo4j.execute_write(
        query,
        {
            "id": item_id,
            "status": body.status,
            "resolved_at": now if body.status != "pending" else None,
            "notes": body.notes,
        },
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Moderation item not found")
    log.info("moderation_item_updated", item_id=item_id, status=body.status)
    return ModerationItemResponse(**rows[0]["props"])


@router.post("/moderation/flag", response_model=ModerationItemResponse, status_code=201)
def flag_content(
    body: ModerationFlagRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> ModerationItemResponse:
    """Flag a hadith or narrator for review."""
    if body.entity_type not in ("hadith", "narrator"):
        raise HTTPException(status_code=400, detail="entity_type must be 'hadith' or 'narrator'")

    now = datetime.now(UTC).isoformat()
    flag_id = f"mod:{body.entity_type}:{body.entity_id}:{now}"
    query = """
        CREATE (m:MODERATION_FLAG {
            id: $id,
            entity_type: $entity_type,
            entity_id: $entity_id,
            reason: $reason,
            status: 'pending',
            flagged_at: $flagged_at
        })
        RETURN properties(m) AS props
    """
    rows = neo4j.execute_write(
        query,
        {
            "id": flag_id,
            "entity_type": body.entity_type,
            "entity_id": body.entity_id,
            "reason": body.reason,
            "flagged_at": now,
        },
    )
    log.info("content_flagged", entity_type=body.entity_type, entity_id=body.entity_id)
    return ModerationItemResponse(**rows[0]["props"])
