"""Historical overlay — link narrators to events via date overlap."""

from __future__ import annotations

from typing import Any

from src.models.enrich import HistoricalResult
from src.utils.logging import get_logger
from src.utils.neo4j_client import Neo4jClient

__all__ = ["run_historical_overlay"]

log = get_logger(__name__)

_MAX_LIFETIME_AH = 120

_FETCH_EVENTS = """\
MATCH (e:HistoricalEvent)
WHERE e.year_start_ah IS NOT NULL AND e.year_end_ah IS NOT NULL
RETURN e.id AS id, e.year_start_ah AS year_start_ah, e.year_end_ah AS year_end_ah
"""

_FETCH_NARRATORS = """\
MATCH (n:Narrator)
WHERE n.birth_year_ah IS NOT NULL AND n.death_year_ah IS NOT NULL
RETURN n.id AS id, n.birth_year_ah AS birth_year_ah, n.death_year_ah AS death_year_ah
"""

_COUNT_NARRATORS_NO_DATES = """\
MATCH (n:Narrator)
WHERE n.birth_year_ah IS NULL OR n.death_year_ah IS NULL
RETURN count(n) AS cnt
"""

_MERGE_ACTIVE_DURING = """\
UNWIND $batch AS row
MATCH (n:Narrator {id: row.narrator_id})
MATCH (e:HistoricalEvent {id: row.event_id})
MERGE (n)-[:ACTIVE_DURING]->(e)
"""


def run_historical_overlay(client: Neo4jClient) -> HistoricalResult:
    """Create ACTIVE_DURING edges between narrators and historical events.

    For each narrator-event pair, checks whether the narrator's active period
    (birth_year_ah to death_year_ah) overlaps with the event period.
    Narrators with lifespan > 120 AH are skipped as a data-quality filter.
    """
    events = client.execute_read(_FETCH_EVENTS)
    narrators = client.execute_read(_FETCH_NARRATORS)
    no_dates_result = client.execute_read(_COUNT_NARRATORS_NO_DATES)
    narrators_skipped_no_dates: int = no_dates_result[0]["cnt"] if no_dates_result else 0

    log.info(
        "historical_overlay_inputs",
        events=len(events),
        narrators_with_dates=len(narrators),
        narrators_no_dates=narrators_skipped_no_dates,
    )

    # Filter narrators with unrealistic lifespans
    narrators_skipped_max_lifetime = 0
    valid_narrators: list[dict[str, Any]] = []
    for nar in narrators:
        lifespan = nar["death_year_ah"] - nar["birth_year_ah"]
        if lifespan > _MAX_LIFETIME_AH:
            narrators_skipped_max_lifetime += 1
            continue
        valid_narrators.append(nar)

    log.info(
        "historical_overlay_filtered",
        valid_narrators=len(valid_narrators),
        skipped_max_lifetime=narrators_skipped_max_lifetime,
    )

    # Build overlap batch
    batch: list[dict[str, str]] = []
    linked_narrators: set[str] = set()
    linked_events: set[str] = set()

    for nar in valid_narrators:
        n_birth = nar["birth_year_ah"]
        n_death = nar["death_year_ah"]
        for evt in events:
            e_start = evt["year_start_ah"]
            e_end = evt["year_end_ah"]
            # Overlap: narrator alive during any part of the event
            if n_birth <= e_end and n_death >= e_start:
                batch.append({"narrator_id": nar["id"], "event_id": evt["id"]})
                linked_narrators.add(nar["id"])
                linked_events.add(evt["id"])

    edges_created = client.execute_write_batch(_MERGE_ACTIVE_DURING, batch) if batch else 0

    # Log edge distribution
    if linked_narrators:
        events_per_narrator: dict[str, int] = {}
        narrators_per_event: dict[str, int] = {}
        for row in batch:
            events_per_narrator[row["narrator_id"]] = (
                events_per_narrator.get(row["narrator_id"], 0) + 1
            )
            narrators_per_event[row["event_id"]] = (
                narrators_per_event.get(row["event_id"], 0) + 1
            )

        epn_values = list(events_per_narrator.values())
        npe_values = list(narrators_per_event.values())
        log.info(
            "historical_overlay_distribution",
            events_per_narrator_avg=round(sum(epn_values) / len(epn_values), 2),
            events_per_narrator_max=max(epn_values),
            narrators_per_event_avg=round(sum(npe_values) / len(npe_values), 2),
            narrators_per_event_max=max(npe_values),
        )

    log.info(
        "historical_overlay_complete",
        edges_created=edges_created,
        narrators_linked=len(linked_narrators),
        events_linked=len(linked_events),
    )

    return HistoricalResult(
        edges_created=edges_created,
        narrators_linked=len(linked_narrators),
        events_linked=len(linked_events),
        narrators_skipped_no_dates=narrators_skipped_no_dates,
        narrators_skipped_max_lifetime=narrators_skipped_max_lifetime,
    )
