"""Tests for the historical overlay enrichment stage (src/enrich/historical.py).

These exercise the pure, DB-free pieces (curated-YAML → graph-property mapping,
lifespan-overlap edge computation) plus the orchestration against a fake Neo4j
client that records the Cypher batches. No live Neo4j is required — the live
load against staging is a separate, deferred leg (see the PR's Test Plan).
"""

from __future__ import annotations

from typing import Any

import pytest

from src.enrich.historical import (
    compute_active_during,
    default_events_path,
    event_to_graph_props,
    load_events_from_yaml,
    merge_active_during,
    merge_events,
    run_historical_overlay,
)
from src.models.historical import HistoricalEvent

# --- fakes ------------------------------------------------------------------


class FakeNeo4jClient:
    """Records writes and serves canned reads, mirroring Neo4jClient's surface."""

    def __init__(self, narrators: list[dict[str, Any]] | None = None) -> None:
        self._narrators = narrators or []
        self.constraints_ensured = False
        self.write_batches: list[tuple[str, list[dict[str, Any]]]] = []

    def ensure_constraints(self) -> None:
        self.constraints_ensured = True

    def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return list(self._narrators)

    def execute_write_batch(
        self, query: str, batch: list[dict[str, Any]], batch_size: int = 1000
    ) -> int:
        self.write_batches.append((query, batch))
        # Stand in for nodes_created + relationships_created.
        return len(batch)


def _event(
    event_id: str,
    *,
    year_start_ah: int,
    year_end_ah: int | None = None,
    event_type: str = "caliphate",
) -> HistoricalEvent:
    return HistoricalEvent.model_validate(
        {
            "id": event_id,
            "name_en": event_id,
            "year_start_ah": year_start_ah,
            "year_end_ah": year_end_ah,
            "year_start_ce": year_start_ah + 621,
            "year_end_ce": (year_end_ah or year_start_ah) + 621,
            "type": event_type,
        }
    )


# --- curated data loads & validates -----------------------------------------


def test_curated_events_file_loads_and_validates() -> None:
    events = load_events_from_yaml(default_events_path())
    assert len(events) >= 10
    ids = {e.id for e in events}
    assert "evt:rashidun-caliphate" in ids
    assert "evt:mihna" in ids


# --- graph property mapping (the schema bridge) -----------------------------


def test_event_to_graph_props_maps_api_read_names() -> None:
    event = _event("evt:x", year_start_ah=11, year_end_ah=40, event_type="fitna")
    props = event_to_graph_props(event)

    # These are exactly the property names src/api/routes/timeline.py reads.
    assert props["id"] == "evt:x"
    assert props["name"] == "evt:x"
    assert props["year_ah"] == 11
    assert props["end_year_ah"] == 40
    assert props["event_type"] == "fitna"
    assert "description" in props
    assert "name_ar" in props


def test_event_to_graph_props_event_type_is_serialized_string() -> None:
    props = event_to_graph_props(_event("evt:x", year_start_ah=11))
    assert isinstance(props["event_type"], str)


# --- lifespan overlap -------------------------------------------------------


def test_overlap_links_narrator_within_event_range() -> None:
    events = [_event("evt:a", year_start_ah=40, year_end_ah=60)]
    narrators = [{"id": "nar:1", "birth_year_ah": 30, "death_year_ah": 70}]
    edges, no_dates, max_life = compute_active_during(narrators, events)
    assert {(e.narrator_id, e.event_id) for e in edges} == {("nar:1", "evt:a")}
    assert no_dates == 0
    assert max_life == 0


def test_overlap_excludes_non_overlapping_narrator() -> None:
    events = [_event("evt:a", year_start_ah=40, year_end_ah=60)]
    # Lived and died well before the event window.
    narrators = [{"id": "nar:1", "birth_year_ah": 1, "death_year_ah": 20}]
    edges, _, _ = compute_active_during(narrators, events)
    assert edges == []


def test_single_year_event_uses_start_for_both_ends() -> None:
    events = [_event("evt:karbala", year_start_ah=61, year_end_ah=61)]
    narrators = [{"id": "nar:1", "birth_year_ah": 4, "death_year_ah": 61}]
    edges, _, _ = compute_active_during(narrators, events)
    assert {e.event_id for e in edges} == {"evt:karbala"}


def test_death_only_narrator_is_linked_via_estimated_window() -> None:
    # Common hadith-bio case: only the death year is recorded.
    events = [_event("evt:mihna", year_start_ah=218, year_end_ah=234)]
    narrators = [{"id": "nar:hanbal", "birth_year_ah": None, "death_year_ah": 241}]
    edges, no_dates, _ = compute_active_during(narrators, events)
    assert {e.narrator_id for e in edges} == {"nar:hanbal"}
    assert no_dates == 0


def test_narrator_with_no_dates_is_skipped() -> None:
    events = [_event("evt:a", year_start_ah=40)]
    narrators = [{"id": "nar:1", "birth_year_ah": None, "death_year_ah": None}]
    edges, no_dates, max_life = compute_active_during(narrators, events)
    assert edges == []
    assert no_dates == 1
    assert max_life == 0


def test_implausible_lifespan_is_skipped_as_max_lifetime() -> None:
    events = [_event("evt:a", year_start_ah=40)]
    # 300-year span with both ends present → bad data.
    narrators = [{"id": "nar:1", "birth_year_ah": 10, "death_year_ah": 310}]
    edges, no_dates, max_life = compute_active_during(narrators, events)
    assert edges == []
    assert no_dates == 0
    assert max_life == 1


def test_narrator_links_to_multiple_overlapping_events() -> None:
    events = [
        _event("evt:a", year_start_ah=11, year_end_ah=40),
        _event("evt:b", year_start_ah=41, year_end_ah=132),
        _event("evt:c", year_start_ah=200, year_end_ah=260),
    ]
    narrators = [{"id": "nar:1", "birth_year_ah": 20, "death_year_ah": 90}]
    edges, _, _ = compute_active_during(narrators, events)
    assert {e.event_id for e in edges} == {"evt:a", "evt:b"}


# --- merge helpers ----------------------------------------------------------


def test_merge_active_during_emits_bare_edge_rows_only() -> None:
    client = FakeNeo4jClient()
    events = [_event("evt:a", year_start_ah=40, year_end_ah=60)]
    narrators = [{"id": "nar:1", "birth_year_ah": 30, "death_year_ah": 70}]
    edges, _, _ = compute_active_during(narrators, events)

    created = merge_active_during(client, edges)  # type: ignore[arg-type]

    assert created == 1
    _, batch = client.write_batches[0]
    # Only the two keys needed for MATCH+MERGE — no null role/affiliation that
    # would risk the null-property-in-MERGE loader bug.
    assert batch == [{"narrator_id": "nar:1", "event_id": "evt:a"}]


def test_merge_events_empty_is_noop() -> None:
    client = FakeNeo4jClient()
    assert merge_events(client, []) == 0  # type: ignore[arg-type]
    assert client.write_batches == []


# --- orchestration ----------------------------------------------------------


def test_run_historical_overlay_loads_events_and_links(tmp_path: Any) -> None:
    yaml_path = tmp_path / "events.yaml"
    yaml_path.write_text(
        """
events:
  - id: "evt:a"
    name_en: "Event A"
    year_start_ah: 40
    year_end_ah: 60
    year_start_ce: 661
    year_end_ce: 681
    type: "caliphate"
""",
        encoding="utf-8",
    )
    client = FakeNeo4jClient(
        narrators=[
            {"id": "nar:1", "birth_year_ah": 30, "death_year_ah": 70},
            {"id": "nar:2", "birth_year_ah": None, "death_year_ah": None},
        ]
    )

    result = run_historical_overlay(client, yaml_path)  # type: ignore[arg-type]

    assert client.constraints_ensured is True
    assert result.events_linked == 1
    assert result.narrators_linked == 1
    assert result.edges_created == 1
    assert result.narrators_skipped_no_dates == 1
    assert result.narrators_skipped_max_lifetime == 0
    # First batch is the event-node MERGE, second is the ACTIVE_DURING MERGE.
    assert len(client.write_batches) == 2


def test_run_historical_overlay_idempotent_with_no_narrators() -> None:
    """Events still load even when the graph has no narrators yet (#963)."""
    client = FakeNeo4jClient(narrators=[])
    result = run_historical_overlay(client, default_events_path())  # type: ignore[arg-type]
    assert result.edges_created == 0
    assert result.narrators_linked == 0
    # Event nodes were still MERGEd.
    event_batch = client.write_batches[0][1]
    assert len(event_batch) >= 10


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
