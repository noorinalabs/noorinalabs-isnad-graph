"""Timeline data endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_neo4j
from src.api.models import (
    NarratorTimelineEntry,
    NarratorTimelineResponse,
    TimelineEntry,
    TimelineRangeResponse,
    TimelineResponse,
)
from src.enrich.historical import DEFAULT_ASSUMED_LIFESPAN_AH, _active_window
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()

# Precision value (``DatePrecision.TABAQA_ESTIMATE``) that marks a window whose
# bounds were derived from the narrator's ṭabaqa rather than an attested year.
_TABAQA_PRECISION = "tabaqa_estimate"


def _narrator_lane(row: dict[str, Any]) -> NarratorTimelineEntry | None:
    """Build a narrator lifespan/ṭabaqa lane from a Cypher result row.

    Returns ``None`` for an undated narrator (no birth or death signal in any
    form) — it cannot be placed on a lane, so the endpoint omits it gracefully.

    A lane is flagged ``estimated`` when either endpoint had to be filled from
    the assumed-lifespan span (only one real bound is known) OR when the
    governing precision is a ṭabaqa estimate. Per the owner decision (ig#1041),
    ṭabaqa-estimated windows are still returned — clearly marked — alongside the
    attested ones.
    """
    window = _active_window(row, DEFAULT_ASSUMED_LIFESPAN_AH)
    if window is None:
        return None
    start, end = window

    # Mirror _active_window's endpoint selection: resolved bound else point year.
    birth_known = (
        row.get("birth_year_ah_earliest") is not None or row.get("birth_year_ah") is not None
    )
    death_known = (
        row.get("death_year_ah_latest") is not None or row.get("death_year_ah") is not None
    )
    tabaqa_estimated = _TABAQA_PRECISION in (
        row.get("birth_date_precision"),
        row.get("death_date_precision"),
    )
    estimated = not (birth_known and death_known) or tabaqa_estimated

    return NarratorTimelineEntry(
        narrator_id=row["id"],
        name_ar=row.get("name_ar"),
        name_en=row.get("name_en"),
        birth_year_ah=row.get("birth_year_ah"),
        death_year_ah=row.get("death_year_ah"),
        window_start_ah=start,
        window_end_ah=end,
        birth_date_precision=row.get("birth_date_precision"),
        death_date_precision=row.get("death_date_precision"),
        tabaqat_class=row.get("tabaqat_class"),
        estimated=estimated,
    )


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


@router.get("/timeline/narrators", response_model=NarratorTimelineResponse)
def get_timeline_narrators(
    start_year: int | None = Query(
        None, description="Only narrators whose active window overlaps at/after this year AH"
    ),
    end_year: int | None = Query(
        None, description="Only narrators whose active window overlaps at/before this year AH"
    ),
    limit: int = Query(500, ge=1, le=2000, description="Max narrators to return"),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> NarratorTimelineResponse:
    """Return narrator lifespan / ṭabaqa lanes for the timeline visualization.

    Serves the resolved narrator date bounds loaded by ig#1039 — earliest birth
    to latest death, plus precision and ṭabaqat class — as [start, end] windows
    suitable for timeline lanes. Undated narrators (no birth or death signal in
    any form) are omitted; ṭabaqa-estimated and lifespan-filled windows are
    returned with ``estimated=True`` so the UI can mark them (owner decision).
    """
    rows = neo4j.execute_read(
        """
        MATCH (n:Narrator)
        WHERE n.birth_year_ah IS NOT NULL OR n.death_year_ah IS NOT NULL
           OR n.birth_year_ah_earliest IS NOT NULL OR n.death_year_ah_latest IS NOT NULL
        RETURN n.id AS id, n.name_ar AS name_ar, n.name_en AS name_en,
               n.birth_year_ah AS birth_year_ah, n.death_year_ah AS death_year_ah,
               n.birth_year_ah_earliest AS birth_year_ah_earliest,
               n.birth_year_ah_latest AS birth_year_ah_latest,
               n.death_year_ah_earliest AS death_year_ah_earliest,
               n.death_year_ah_latest AS death_year_ah_latest,
               n.birth_date_precision AS birth_date_precision,
               n.death_date_precision AS death_date_precision,
               n.tabaqat_class AS tabaqat_class
        ORDER BY coalesce(n.death_year_ah_latest, n.death_year_ah,
                          n.birth_year_ah_latest, n.birth_year_ah)
        LIMIT $limit
        """,
        {"limit": limit},
    )

    entries: list[NarratorTimelineEntry] = []
    for row in rows:
        lane = _narrator_lane(row)
        if lane is None:
            continue
        # Viewport filter: keep lanes whose [start, end] window overlaps the
        # requested [start_year, end_year] range.
        if start_year is not None and lane.window_end_ah < start_year:
            continue
        if end_year is not None and lane.window_start_ah > end_year:
            continue
        entries.append(lane)

    return NarratorTimelineResponse(entries=entries, total=len(entries))
