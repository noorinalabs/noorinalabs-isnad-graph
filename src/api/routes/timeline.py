"""Timeline data endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_neo4j
from src.api.models import TimelineEntry, TimelineRangeResponse, TimelineResponse
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


@router.get("/timeline/range", response_model=TimelineRangeResponse)
def get_timeline_range(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> TimelineRangeResponse:
    """Return the min/max year_ah range from HistoricalEvent nodes."""
    rows = neo4j.execute_read(
        """
        MATCH (e:HistoricalEvent)
        RETURN min(e.year_ah) AS min_year, max(coalesce(e.end_year_ah, e.year_ah)) AS max_year
        """,
        {},
    )
    if rows and rows[0]["min_year"] is not None:
        return TimelineRangeResponse(
            min_year_ah=rows[0]["min_year"],
            max_year_ah=rows[0]["max_year"],
        )
    return TimelineRangeResponse(min_year_ah=0, max_year_ah=300)


@router.get("/timeline", response_model=TimelineResponse)
def get_timeline(
    start_year: int | None = Query(None, description="Start year AH (inclusive)"),
    end_year: int | None = Query(None, description="End year AH (inclusive)"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(100, ge=1, le=500, description="Items per page"),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> TimelineResponse:
    """Return historical events with narrator counts per period for timeline visualization."""
    skip = (page - 1) * limit

    # Total count of events matching the year filter, before SKIP/LIMIT
    # pagination, so clients can paginate over the full result set.
    count_rows = neo4j.execute_read(
        """
        MATCH (e:HistoricalEvent)
        WHERE ($start_year IS NULL OR e.year_ah >= $start_year)
          AND ($end_year IS NULL OR e.year_ah <= $end_year)
        RETURN count(e) AS total
        """,
        {"start_year": start_year, "end_year": end_year},
    )
    total = count_rows[0]["total"] if count_rows else 0

    rows = neo4j.execute_read(
        """
        MATCH (e:HistoricalEvent)
        WHERE ($start_year IS NULL OR e.year_ah >= $start_year)
          AND ($end_year IS NULL OR e.year_ah <= $end_year)
        OPTIONAL MATCH (n:Narrator)-[:ACTIVE_DURING]->(e)
        RETURN e.id AS id, e.name AS name, e.name_ar AS name_ar,
               e.year_ah AS year_ah, e.end_year_ah AS end_year_ah,
               e.event_type AS event_type, e.description AS description,
               count(DISTINCT n) AS narrator_count
        ORDER BY e.year_ah
        SKIP $skip
        LIMIT $limit
        """,
        {
            "start_year": start_year,
            "end_year": end_year,
            "skip": skip,
            "limit": limit,
        },
    )

    entries = [
        TimelineEntry(
            id=r["id"],
            name=r.get("name", ""),
            name_ar=r.get("name_ar"),
            year_ah=r["year_ah"],
            end_year_ah=r.get("end_year_ah"),
            event_type=r.get("event_type"),
            description=r.get("description"),
            narrator_count=r.get("narrator_count", 0),
        )
        for r in rows
    ]
    return TimelineResponse(entries=entries, total=total)
