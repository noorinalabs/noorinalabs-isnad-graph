"""Historical overlay — link narrators and compilers to events via date overlap."""

from __future__ import annotations

import bisect
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

_FETCH_COMPILERS = """\
MATCH (c:Collection)
WHERE c.compilation_year_ah IS NOT NULL
RETURN c.id AS id, c.compilation_year_ah AS compilation_year_ah,
       c.compiler_name AS compiler_name
"""

_MERGE_ACTIVE_DURING_NARRATOR = """\
UNWIND $batch AS row
MATCH (n:Narrator {id: row.narrator_id})
MATCH (e:HistoricalEvent {id: row.event_id})
MERGE (n)-[:ACTIVE_DURING]->(e)
"""

_MERGE_ACTIVE_DURING_COMPILER = """\
UNWIND $batch AS row
MATCH (c:Collection {id: row.compiler_id})
MATCH (e:HistoricalEvent {id: row.event_id})
MERGE (c)-[:ACTIVE_DURING]->(e)
"""


def _compute_overlap_batch(
    entities: list[dict[str, Any]],
    sorted_events: list[dict[str, Any]],
    event_starts: list[int],
    entity_id_key: str,
    batch_id_key: str,
) -> tuple[list[dict[str, str]], set[str], set[str]]:
    """Compute ACTIVE_DURING overlap batch for a set of entities.

    Uses binary search on sorted events to efficiently find overlapping
    event periods for each entity's lifetime.
    """
    batch: list[dict[str, str]] = []
    linked_entities: set[str] = set()
    linked_events: set[str] = set()

    for ent in entities:
        n_birth = ent["birth_year_ah"]
        n_death = ent["death_year_ah"]
        # Only consider events whose start year <= entity's death year
        upper = bisect.bisect_right(event_starts, n_death)
        for idx in range(upper):
            evt = sorted_events[idx]
            e_end = evt["year_end_ah"]
            # Overlap: entity alive during any part of the event
            if n_death >= evt["year_start_ah"] and n_birth <= e_end:
                batch.append({batch_id_key: ent[entity_id_key], "event_id": evt["id"]})
                linked_entities.add(ent[entity_id_key])
                linked_events.add(evt["id"])

    return batch, linked_entities, linked_events


def _log_distribution(
    batch: list[dict[str, str]],
    entity_key: str,
    entity_label: str,
) -> None:
    """Log edge distribution statistics for a batch."""
    if not batch:
        return
    events_per_entity: dict[str, int] = {}
    entities_per_event: dict[str, int] = {}
    for row in batch:
        events_per_entity[row[entity_key]] = events_per_entity.get(row[entity_key], 0) + 1
        entities_per_event[row["event_id"]] = entities_per_event.get(row["event_id"], 0) + 1

    epe_values = list(events_per_entity.values())
    npe_values = list(entities_per_event.values())
    log.info(
        f"historical_overlay_{entity_label}_distribution",
        events_per_entity_avg=round(sum(epe_values) / len(epe_values), 2),
        events_per_entity_max=max(epe_values),
        entities_per_event_avg=round(sum(npe_values) / len(npe_values), 2),
        entities_per_event_max=max(npe_values),
    )


def run_historical_overlay(client: Neo4jClient) -> HistoricalResult:
    """Create ACTIVE_DURING edges between narrators/compilers and historical events.

    For each narrator-event pair, checks whether the narrator's active period
    (birth_year_ah to death_year_ah) overlaps with the event period.
    Narrators with lifespan > 120 AH are skipped as a data-quality filter.

    Compilers (collections) are matched using compilation_year_ah as a proxy
    for the compiler's active period. A ±30 year window around the compilation
    year is used to approximate the compiler's scholarly active years.
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

    # Build overlap batch — sort events by start year and use binary search
    sorted_events = sorted(events, key=lambda e: e["year_start_ah"])
    event_starts = [e["year_start_ah"] for e in sorted_events]

    # --- Narrator ACTIVE_DURING edges ---
    narrator_batch, linked_narrators, linked_events_nar = _compute_overlap_batch(
        valid_narrators,
        sorted_events,
        event_starts,
        entity_id_key="id",
        batch_id_key="narrator_id",
    )

    narrator_edges = (
        client.execute_write_batch(_MERGE_ACTIVE_DURING_NARRATOR, narrator_batch)
        if narrator_batch
        else 0
    )
    _log_distribution(narrator_batch, "narrator_id", "narrator")

    log.info(
        "historical_overlay_narrators_complete",
        edges_created=narrator_edges,
        narrators_linked=len(linked_narrators),
        events_linked=len(linked_events_nar),
    )

    # --- Compiler ACTIVE_DURING edges ---
    # Use compilation_year_ah ± 30 as proxy for compiler active period
    _COMPILER_WINDOW_AH = 30
    compilers_raw = client.execute_read(_FETCH_COMPILERS)
    compiler_entities: list[dict[str, Any]] = []
    for comp in compilers_raw:
        year = comp["compilation_year_ah"]
        compiler_entities.append(
            {
                "id": comp["id"],
                "birth_year_ah": max(1, year - _COMPILER_WINDOW_AH),
                "death_year_ah": year + _COMPILER_WINDOW_AH,
            }
        )

    compiler_batch, linked_compilers, linked_events_comp = _compute_overlap_batch(
        compiler_entities,
        sorted_events,
        event_starts,
        entity_id_key="id",
        batch_id_key="compiler_id",
    )

    compiler_edges = (
        client.execute_write_batch(_MERGE_ACTIVE_DURING_COMPILER, compiler_batch)
        if compiler_batch
        else 0
    )
    _log_distribution(compiler_batch, "compiler_id", "compiler")

    log.info(
        "historical_overlay_compilers_complete",
        edges_created=compiler_edges,
        compilers_linked=len(linked_compilers),
        events_linked=len(linked_events_comp),
    )

    total_edges = narrator_edges + compiler_edges
    all_linked_events = linked_events_nar | linked_events_comp

    log.info(
        "historical_overlay_complete",
        total_edges_created=total_edges,
        narrator_edges=narrator_edges,
        compiler_edges=compiler_edges,
        narrators_linked=len(linked_narrators),
        compilers_linked=len(linked_compilers),
        events_linked=len(all_linked_events),
    )

    return HistoricalResult(
        edges_created=total_edges,
        narrators_linked=len(linked_narrators),
        compilers_linked=len(linked_compilers),
        events_linked=len(all_linked_events),
        narrators_skipped_no_dates=narrators_skipped_no_dates,
        narrators_skipped_max_lifetime=narrators_skipped_max_lifetime,
    )
