"""Historical overlay enrichment — load HistoricalEvent nodes and link narrators.

This stage closes the gap behind isnad-graph#965 (the "Historical Events /
Narrator Activity" panel rendered empty because no ``HistoricalEvent`` nodes
were ever loaded). It does two things against the loaded graph:

1. **Load reference events** — read the curated event set from
   ``data/curated/historical_events.yaml`` and ``MERGE`` one ``HistoricalEvent``
   node per event. The curated YAML uses the *model* field names
   (``name_en`` / ``year_start_ah`` / ``type``); the graph (and the
   ``/timeline`` API that reads it) uses ``name`` / ``year_ah`` / ``event_type``.
   :func:`event_to_graph_props` is the single bridge between the two schemas — if
   the API query in ``src/api/routes/timeline.py`` changes a property name, this
   mapping is the one place to update.

2. **Link narrators by lifespan** — create ``ACTIVE_DURING`` edges from every
   narrator whose active lifespan overlaps an event's date range. The overlap is
   computed in pure Python (:func:`compute_active_during`) so it is unit-testable
   without a live Neo4j; only the final ``MERGE`` of the resolved edge list
   touches the database.

The ``ACTIVE_DURING`` relationship is ``MERGE``d as a *bare* edge (no properties
in the pattern) to avoid the null-property-in-MERGE loader bug that bit the
``APPEARS_IN`` loader (main#139): Neo4j rejects a ``MERGE`` whose pattern carries
a null property, and lifespan-derived edges have no ``role`` / ``affiliation``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from src.models.edges import ActiveDuring
from src.models.enrich import HistoricalResult
from src.models.historical import HistoricalEvent
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.utils.neo4j_client import Neo4jClient

__all__ = [
    "DEFAULT_ASSUMED_LIFESPAN_AH",
    "MAX_NARRATOR_LIFETIME_AH",
    "compute_active_during",
    "default_events_path",
    "event_to_graph_props",
    "load_events_from_yaml",
    "run_historical_overlay",
]

log = get_logger(__name__)

# When only one of a narrator's birth/death years is known we estimate the other
# end of their active window using this span (in Hijri years). Hadith narrator
# biographies reliably record the death year (wafat) but rarely the birth year,
# so anchoring on a known year and estimating the window keeps the overlay
# useful instead of skipping the majority of narrators.
DEFAULT_ASSUMED_LIFESPAN_AH = 80

# A computed lifespan wider than this (only reachable when BOTH years are
# present) is treated as bad data and the narrator is skipped rather than linked
# to an implausibly long stretch of events.
MAX_NARRATOR_LIFETIME_AH = 120

# Cypher MERGEs one HistoricalEvent per row keyed on id, then SET-merges the
# remaining graph properties. MERGE keys only on ``id`` (always present), so the
# null-property-in-MERGE-pattern bug cannot occur here.
_MERGE_EVENTS_QUERY = """
UNWIND $batch AS row
MERGE (e:HistoricalEvent {id: row.id})
SET e += row
"""

# Bare ACTIVE_DURING edge — no properties in the MERGE pattern (see module docstring).
_MERGE_ACTIVE_DURING_QUERY = """
UNWIND $batch AS row
MATCH (n:Narrator {id: row.narrator_id})
MATCH (e:HistoricalEvent {id: row.event_id})
MERGE (n)-[:ACTIVE_DURING]->(e)
"""

_FETCH_NARRATORS_QUERY = """
MATCH (n:Narrator)
RETURN n.id AS id,
       n.birth_year_ah AS birth_year_ah,
       n.death_year_ah AS death_year_ah
"""


def default_events_path() -> Path:
    """Return the repo-relative path to the curated historical events YAML."""
    return Path(__file__).resolve().parents[2] / "data" / "curated" / "historical_events.yaml"


def load_events_from_yaml(path: Path | None = None) -> list[HistoricalEvent]:
    """Parse and validate the curated historical events.

    Each entry is validated through the :class:`HistoricalEvent` model, so a
    malformed curated file fails fast here rather than producing partial graph
    state.
    """
    events_path = path or default_events_path()
    raw = yaml.safe_load(events_path.read_text(encoding="utf-8")) or {}
    entries = raw.get("events", [])
    return [HistoricalEvent.model_validate(entry) for entry in entries]


def event_to_graph_props(event: HistoricalEvent) -> dict[str, Any]:
    """Map a :class:`HistoricalEvent` to the graph property names the API reads.

    The ``/timeline`` and ``/timeline/range`` endpoints read ``id``, ``name``,
    ``name_ar``, ``year_ah``, ``end_year_ah``, ``event_type`` and ``description``
    off the node. The curated model uses different names; this is the single
    place that bridges them.
    """
    return {
        "id": event.id,
        "name": event.name_en,
        "name_ar": event.name_ar,
        "year_ah": event.year_start_ah,
        "end_year_ah": event.year_end_ah,
        "event_type": event.event_type.value,
        "description": event.description,
        # Carried through for richer rendering; not required by the API today.
        "caliphate": event.caliphate,
        "region": event.region,
        "year_ce": event.year_start_ce,
        "end_year_ce": event.year_end_ce,
    }


def _active_window(
    birth_year_ah: int | None,
    death_year_ah: int | None,
    assumed_lifespan_ah: int,
) -> tuple[int, int] | None:
    """Resolve a narrator's [start, end] active window in Hijri years.

    Returns ``None`` when neither year is known (the narrator cannot be placed in
    time). When only one year is known the other end is estimated using
    ``assumed_lifespan_ah``.
    """
    if birth_year_ah is None and death_year_ah is None:
        return None
    if death_year_ah is None:
        # Only birth known.
        assert birth_year_ah is not None
        return birth_year_ah, birth_year_ah + assumed_lifespan_ah
    if birth_year_ah is None:
        # Only death known — the common case for hadith narrators.
        return death_year_ah - assumed_lifespan_ah, death_year_ah
    return birth_year_ah, death_year_ah


def compute_active_during(
    narrators: list[dict[str, Any]],
    events: list[HistoricalEvent],
    *,
    assumed_lifespan_ah: int = DEFAULT_ASSUMED_LIFESPAN_AH,
    max_lifetime_ah: int = MAX_NARRATOR_LIFETIME_AH,
) -> tuple[list[ActiveDuring], int, int]:
    """Compute ACTIVE_DURING edges by lifespan overlap (pure, DB-free).

    A narrator is active during an event when their resolved active window
    overlaps the event's ``[year_start_ah, year_end_ah]`` range (a single-year
    event uses ``year_start_ah`` for both ends).

    Returns ``(edges, skipped_no_dates, skipped_max_lifetime)``.
    """
    edges: list[ActiveDuring] = []
    skipped_no_dates = 0
    skipped_max_lifetime = 0

    for narrator in narrators:
        window = _active_window(
            narrator.get("birth_year_ah"),
            narrator.get("death_year_ah"),
            assumed_lifespan_ah,
        )
        if window is None:
            skipped_no_dates += 1
            continue
        active_start, active_end = window
        if active_end - active_start > max_lifetime_ah:
            skipped_max_lifetime += 1
            continue

        narrator_id = narrator["id"]
        for event in events:
            event_start = event.year_start_ah
            event_end = event.year_end_ah if event.year_end_ah is not None else event.year_start_ah
            # Half-open-free interval overlap: born on/before the event ends and
            # still active on/after the event starts.
            if active_start <= event_end and active_end >= event_start:
                edges.append(ActiveDuring(narrator_id=narrator_id, event_id=event.id))

    return edges, skipped_no_dates, skipped_max_lifetime


def merge_events(client: Neo4jClient, events: list[HistoricalEvent]) -> int:
    """MERGE the HistoricalEvent reference nodes. Returns nodes created."""
    batch = [event_to_graph_props(event) for event in events]
    if not batch:
        return 0
    return client.execute_write_batch(_MERGE_EVENTS_QUERY, batch)


def merge_active_during(client: Neo4jClient, edges: list[ActiveDuring]) -> int:
    """MERGE the ACTIVE_DURING edges. Returns relationships created."""
    if not edges:
        return 0
    batch = [{"narrator_id": e.narrator_id, "event_id": e.event_id} for e in edges]
    return client.execute_write_batch(_MERGE_ACTIVE_DURING_QUERY, batch)


def run_historical_overlay(
    client: Neo4jClient,
    events_path: Path | None = None,
    *,
    assumed_lifespan_ah: int = DEFAULT_ASSUMED_LIFESPAN_AH,
    max_lifetime_ah: int = MAX_NARRATOR_LIFETIME_AH,
) -> HistoricalResult:
    """Load HistoricalEvent nodes and link narrators by lifespan overlap.

    Idempotent: every write is a ``MERGE``, so re-running reconciles state rather
    than duplicating it.
    """
    events = load_events_from_yaml(events_path)
    client.ensure_constraints()

    nodes_created = merge_events(client, events)

    narrators = client.execute_read(_FETCH_NARRATORS_QUERY)
    edges, skipped_no_dates, skipped_max_lifetime = compute_active_during(
        narrators,
        events,
        assumed_lifespan_ah=assumed_lifespan_ah,
        max_lifetime_ah=max_lifetime_ah,
    )
    edges_created = merge_active_during(client, edges)

    result = HistoricalResult(
        edges_created=edges_created,
        narrators_linked=len({e.narrator_id for e in edges}),
        events_linked=len({e.event_id for e in edges}),
        narrators_skipped_no_dates=skipped_no_dates,
        narrators_skipped_max_lifetime=skipped_max_lifetime,
    )
    log.info(
        "historical_overlay_complete",
        events_total=len(events),
        event_nodes_created=nodes_created,
        narrators_seen=len(narrators),
        edges_created=edges_created,
        narrators_linked=result.narrators_linked,
        events_linked=result.events_linked,
        narrators_skipped_no_dates=skipped_no_dates,
        narrators_skipped_max_lifetime=skipped_max_lifetime,
    )
    return result
