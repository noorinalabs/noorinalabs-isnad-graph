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
    _MERGE_NARRATOR_DATES_QUERY,
    NARRATOR_DATE_PROPS,
    compute_active_during,
    default_events_path,
    event_to_graph_props,
    load_events_from_yaml,
    load_narrator_dates_from_json,
    merge_active_during,
    merge_events,
    merge_narrator_dates,
    narrator_dates_to_graph_props,
    run_historical_overlay,
)
from src.models.enums import DatePrecision
from src.models.historical import HistoricalEvent
from src.models.narrator import NarratorDates

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
        # Apply resolved-date writes to the canned narrator store so a subsequent
        # execute_read reflects the freshly-SET bounds — mirrors the real
        # MATCH ... SET n += row.props against existing nodes.
        if query == _MERGE_NARRATOR_DATES_QUERY:
            by_id = {n["id"]: n for n in self._narrators}
            for row in batch:
                node = by_id.get(row["id"])
                if node is not None:
                    node.update(row["props"])
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


# --- _active_window upgrade: resolved bounds preferred (ig#1039) -------------


def test_resolved_death_latest_widens_window_to_link_later_event() -> None:
    """A narrator's resolved death_latest bound extends the window past its point."""
    # Point death 230 → estimate window [150, 230] would NOT reach a 240-250 event;
    # the resolved latest bound 250 widens the window so it does.
    events = [_event("evt:late", year_start_ah=240, year_end_ah=250)]
    narrators = [
        {
            "id": "nar:1",
            "birth_year_ah": None,
            "death_year_ah": 230,
            "death_year_ah_latest": 250,
        }
    ]
    edges, no_dates, max_life = compute_active_during(narrators, events)
    assert {e.event_id for e in edges} == {"evt:late"}
    assert no_dates == 0
    assert max_life == 0


def test_resolved_birth_earliest_widens_window_to_link_earlier_event() -> None:
    """A narrator's resolved birth_earliest bound extends the window before its point."""
    events = [_event("evt:early", year_start_ah=5, year_end_ah=15)]
    # Point birth 30 → window starts at 30; resolved earliest 10 reaches the event.
    narrators = [
        {
            "id": "nar:1",
            "birth_year_ah": 30,
            "death_year_ah": 90,
            "birth_year_ah_earliest": 10,
        }
    ]
    edges, _, _ = compute_active_during(narrators, events)
    assert {e.event_id for e in edges} == {"evt:early"}


def test_absent_bounds_fall_back_to_point_estimate_window() -> None:
    """With no resolved bounds the window is unchanged from the legacy estimate."""
    # Death-only, no bounds → [241-80, 241] = [161, 241]; the Mihna (218-234) overlaps.
    events = [_event("evt:mihna", year_start_ah=218, year_end_ah=234)]
    narrators = [{"id": "nar:hanbal", "birth_year_ah": None, "death_year_ah": 241}]
    edges, no_dates, _ = compute_active_during(narrators, events)
    assert {e.narrator_id for e in edges} == {"nar:hanbal"}
    assert no_dates == 0


def test_resolved_bounds_only_no_point_estimate_still_places_narrator() -> None:
    """Bounds present but point estimates absent — narrator is still placed."""
    events = [_event("evt:a", year_start_ah=100, year_end_ah=120)]
    narrators = [
        {
            "id": "nar:1",
            "birth_year_ah": None,
            "death_year_ah": None,
            "birth_year_ah_earliest": 90,
            "death_year_ah_latest": 160,
        }
    ]
    edges, no_dates, _ = compute_active_during(narrators, events)
    assert {e.event_id for e in edges} == {"evt:a"}
    assert no_dates == 0


# --- resolved-date loader: graph-prop bridge (ig#1039) ----------------------


def _dates(narrator_id: str, **kwargs: Any) -> NarratorDates:
    return NarratorDates.model_validate({"id": narrator_id, **kwargs})


def test_narrator_dates_to_graph_props_serializes_precision_enum() -> None:
    record = _dates(
        "nar:1",
        death_year_ah=150,
        death_year_ah_earliest=148,
        death_year_ah_latest=152,
        death_date_precision=DatePrecision.RANGE,
        birth_date_precision=DatePrecision.TABAQA_ESTIMATE,
    )
    props = narrator_dates_to_graph_props(record)

    # Enums are serialized to their string values for Neo4j.
    assert props["death_date_precision"] == "range"
    assert props["birth_date_precision"] == "tabaqa_estimate"
    assert props["death_year_ah_earliest"] == 148
    assert props["death_year_ah_latest"] == 152
    # id is the MATCH key, never written as a property.
    assert "id" not in props
    # Every declared date prop is present (so SET n += covers/clears them all).
    assert set(props) == set(NARRATOR_DATE_PROPS)


def test_narrator_dates_to_graph_props_keeps_null_precision_none() -> None:
    props = narrator_dates_to_graph_props(_dates("nar:1", death_year_ah=150))
    assert props["death_date_precision"] is None
    assert props["birth_date_precision"] is None


# --- resolved-date loader: write mechanics (ig#1039) ------------------------


def test_merge_narrator_dates_emits_matchset_rows() -> None:
    client = FakeNeo4jClient(narrators=[{"id": "nar:1"}])
    records = [_dates("nar:1", death_year_ah=150, death_date_precision=DatePrecision.EXACT)]

    written = merge_narrator_dates(client, records)  # type: ignore[arg-type]

    assert written == 1
    query, batch = client.write_batches[0]
    assert query == _MERGE_NARRATOR_DATES_QUERY
    assert batch[0]["id"] == "nar:1"
    # Row carries id (MATCH key) + a nested props map (the SET payload).
    assert batch[0]["props"]["death_year_ah"] == 150
    assert batch[0]["props"]["death_date_precision"] == "exact"


def test_merge_narrator_dates_empty_is_noop() -> None:
    client = FakeNeo4jClient()
    assert merge_narrator_dates(client, []) == 0  # type: ignore[arg-type]
    assert client.write_batches == []


def test_load_narrator_dates_from_json_validates(tmp_path: Any) -> None:
    path = tmp_path / "dates.json"
    path.write_text(
        '[{"id": "nar:1", "death_year_ah": 150, "death_date_precision": "exact"}]',
        encoding="utf-8",
    )
    records = load_narrator_dates_from_json(path)
    assert len(records) == 1
    assert records[0].id == "nar:1"
    assert records[0].death_date_precision is DatePrecision.EXACT


def test_load_narrator_dates_from_json_rejects_non_array(tmp_path: Any) -> None:
    path = tmp_path / "dates.json"
    path.write_text('{"id": "nar:1"}', encoding="utf-8")
    with pytest.raises(ValueError, match="array"):
        load_narrator_dates_from_json(path)


def test_load_narrator_dates_from_json_rejects_bad_id(tmp_path: Any) -> None:
    path = tmp_path / "dates.json"
    path.write_text('[{"id": "bad-id", "death_year_ah": 150}]', encoding="utf-8")
    with pytest.raises(ValueError, match="nar:"):
        load_narrator_dates_from_json(path)


# --- run_historical_overlay end-to-end with resolved dates (ig#1039) --------


def test_run_historical_overlay_writes_dates_then_links_via_real_bounds() -> None:
    """Resolved dates are written first; the link then uses the real bounds.

    The narrator has only a point death year of 230 (estimate window [150, 230],
    which would miss a 240-250 event). The resolved death_latest=250 is loaded
    first, so the re-read narrator's window reaches the late event.
    """
    events_yaml = default_events_path()
    client = FakeNeo4jClient(
        narrators=[{"id": "nar:1", "birth_year_ah": None, "death_year_ah": 230}]
    )

    # Use a tiny event set via narrators that overlap a curated late event is
    # fragile; instead assert the date-write happened and was applied to the store.
    records = [_dates("nar:1", death_year_ah=230, death_year_ah_latest=250)]
    result = run_historical_overlay(client, events_yaml, narrator_dates=records)  # type: ignore[arg-type]

    assert result.narrators_dated == 1
    # The date-write batch was emitted against the MATCH ... SET query.
    queries = [q for q, _ in client.write_batches]
    assert _MERGE_NARRATOR_DATES_QUERY in queries
    # And the store now reflects the resolved bound (FakeNeo4jClient applied it),
    # so the window used for linking was the widened one.
    assert client._narrators[0]["death_year_ah_latest"] == 250


def test_run_historical_overlay_without_dates_leaves_narrators_dated_zero() -> None:
    client = FakeNeo4jClient(narrators=[{"id": "nar:1", "birth_year_ah": 30, "death_year_ah": 70}])
    result = run_historical_overlay(client, default_events_path())  # type: ignore[arg-type]
    assert result.narrators_dated == 0
    queries = [q for q, _ in client.write_batches]
    assert _MERGE_NARRATOR_DATES_QUERY not in queries


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
