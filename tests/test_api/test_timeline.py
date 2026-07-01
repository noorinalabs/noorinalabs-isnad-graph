"""Tests for timeline endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

SAMPLE_EVENT = {
    "id": "evt-001",
    "name": "Battle of Badr",
    "name_ar": "غزوة بدر",
    "year_ah": 2,
    "end_year_ah": None,
    "event_type": "battle",
    "description": "First major battle.",
    "narrator_count": 3,
}


def test_timeline_empty(client: TestClient) -> None:
    """GET /api/v1/timeline returns empty response when no data."""
    resp = client.get("/api/v1/timeline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert body["total"] == 0


def test_timeline_total_reflects_full_count(client: TestClient, mock_neo4j: MagicMock) -> None:
    """total comes from a dedicated COUNT query, not the page-limited entry list."""
    mock_neo4j.execute_read.side_effect = [
        # count query over the full filtered set
        [{"total": 240}],
        # page-limited data query
        [SAMPLE_EVENT],
    ]
    resp = client.get("/api/v1/timeline?limit=1")
    assert resp.status_code == 200
    body = resp.json()
    # total is the true count (240), not len(entries) which is capped at limit
    assert body["total"] == 240
    assert len(body["entries"]) == 1
    assert body["entries"][0]["id"] == "evt-001"

    # Verify the first query issued is a count query
    count_query = mock_neo4j.execute_read.call_args_list[0][0][0]
    assert "count(e)" in count_query


def test_timeline_count_respects_year_filter(client: TestClient, mock_neo4j: MagicMock) -> None:
    """The COUNT query is passed the same start/end year filter as the data query."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 5}],
        [SAMPLE_EVENT],
    ]
    resp = client.get("/api/v1/timeline?start_year=1&end_year=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5

    count_params = mock_neo4j.execute_read.call_args_list[0][0][1]
    assert count_params["start_year"] == 1
    assert count_params["end_year"] == 10


def test_timeline_range(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/timeline/range returns min/max year from events."""
    mock_neo4j.execute_read.side_effect = [
        [{"min_year": 1, "max_year": 300}],
    ]
    resp = client.get("/api/v1/timeline/range")
    assert resp.status_code == 200
    body = resp.json()
    assert body["min_year_ah"] == 1
    assert body["max_year_ah"] == 300


SAMPLE_NARRATOR_ROW = {
    "id": "malik",
    "name_ar": "مالك بن أنس",
    "name_en": "Malik ibn Anas",
    "birth_year_ah": 93,
    "death_year_ah": 179,
    "birth_year_ah_earliest": None,
    "birth_year_ah_latest": None,
    "death_year_ah_earliest": None,
    "death_year_ah_latest": None,
    "birth_date_precision": "exact",
    "death_date_precision": "exact",
    "tabaqat_class": "7",
}


def test_timeline_narrators_returns_dated(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /timeline/narrators returns a lane with the resolved date window."""
    mock_neo4j.execute_read.side_effect = [[SAMPLE_NARRATOR_ROW]]
    resp = client.get("/api/v1/timeline/narrators")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    entry = body["entries"][0]
    assert entry["narrator_id"] == "malik"
    assert entry["window_start_ah"] == 93
    assert entry["window_end_ah"] == 179
    assert entry["tabaqat_class"] == "7"
    # Both endpoints attested → not an estimated window.
    assert entry["estimated"] is False


def test_timeline_narrators_death_only_is_estimated(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """A death-only narrator gets a lifespan-filled, estimated window."""
    row = {
        **SAMPLE_NARRATOR_ROW,
        "birth_year_ah": None,
        "death_year_ah": 179,
        "birth_date_precision": None,
    }
    mock_neo4j.execute_read.side_effect = [[row]]
    resp = client.get("/api/v1/timeline/narrators")
    assert resp.status_code == 200
    entry = resp.json()["entries"][0]
    assert entry["estimated"] is True
    # DEFAULT_ASSUMED_LIFESPAN_AH == 80 → [179 - 80, 179].
    assert entry["window_start_ah"] == 99
    assert entry["window_end_ah"] == 179


def test_timeline_narrators_tabaqa_estimate_marked(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """Resolved bounds with ṭabaqa-estimate precision are returned but marked."""
    row = {
        **SAMPLE_NARRATOR_ROW,
        "birth_year_ah": None,
        "death_year_ah": None,
        "birth_year_ah_earliest": 90,
        "birth_year_ah_latest": 100,
        "death_year_ah_earliest": 150,
        "death_year_ah_latest": 170,
        "birth_date_precision": "tabaqa_estimate",
        "death_date_precision": "tabaqa_estimate",
    }
    mock_neo4j.execute_read.side_effect = [[row]]
    resp = client.get("/api/v1/timeline/narrators")
    assert resp.status_code == 200
    entry = resp.json()["entries"][0]
    assert entry["window_start_ah"] == 90
    assert entry["window_end_ah"] == 170
    assert entry["estimated"] is True


def test_timeline_narrators_skips_undated(client: TestClient, mock_neo4j: MagicMock) -> None:
    """A row with no date signal in any form is omitted gracefully."""
    undated = {
        **SAMPLE_NARRATOR_ROW,
        "birth_year_ah": None,
        "death_year_ah": None,
        "birth_year_ah_earliest": None,
        "birth_year_ah_latest": None,
        "death_year_ah_earliest": None,
        "death_year_ah_latest": None,
        "birth_date_precision": None,
        "death_date_precision": None,
    }
    mock_neo4j.execute_read.side_effect = [[undated]]
    resp = client.get("/api/v1/timeline/narrators")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert body["total"] == 0


def test_timeline_narrators_empty(client: TestClient, mock_neo4j: MagicMock) -> None:
    """No narrators with dates → empty response."""
    mock_neo4j.execute_read.side_effect = [[]]
    resp = client.get("/api/v1/timeline/narrators")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert body["total"] == 0


def _attested_narrator(narrator_id: str, birth: int, death: int) -> dict[str, object]:
    """A fully-attested narrator row → window == [birth, death], estimated False."""
    return {
        "id": narrator_id,
        "name_ar": narrator_id,
        "name_en": narrator_id,
        "birth_year_ah": birth,
        "death_year_ah": death,
        "birth_year_ah_earliest": None,
        "birth_year_ah_latest": None,
        "death_year_ah_earliest": None,
        "death_year_ah_latest": None,
        "birth_date_precision": "exact",
        "death_date_precision": "exact",
        "tabaqat_class": None,
    }


def _fake_neo4j_viewport(corpus: list[dict[str, object]]):
    """A query-param-aware fake for ``execute_read`` that emulates the endpoint's
    Cypher: viewport WHERE (window-overlap) → ORDER BY death ASC → LIMIT.

    Because the real DB is mocked, this fake is what makes the pre-filter-LIMIT
    bug observable in a unit test: the emulated viewport filter runs *before* the
    LIMIT, keyed off the ``start_year``/``end_year`` params. The buggy route never
    passed those params into Cypher (it filtered in Python *after* the LIMIT), so
    against the buggy route this fake sees no viewport params, returns the global
    earliest-death page, and the late-viewport assertion below fails — exactly the
    regression this test pins.
    """

    def _run(_query: str, params: dict[str, object]) -> list[dict[str, object]]:
        start = params.get("start_year")
        end = params.get("end_year")
        rows = list(corpus)
        # Emulate the in-Cypher window-overlap WHERE (attested seeds: window ==
        # [birth, death]). None means unbounded, mirroring `$x IS NULL OR ...`.
        kept = []
        for r in rows:
            win_start = r["birth_year_ah"]
            win_end = r["death_year_ah"]
            if start is not None and win_end < start:
                continue
            if end is not None and win_start > end:
                continue
            kept.append(r)
        kept.sort(key=lambda r: r["death_year_ah"])  # ORDER BY death ASC
        limit = params.get("limit")
        if limit is not None:
            kept = kept[: int(limit)]
        return kept

    return _run


def test_timeline_narrators_viewport_filters_before_limit(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """A late viewport must return the late-death narrators, not the global
    earliest-death page.

    Regression for the pre-filter-LIMIT bug (both reviewers, ig#1041): on the real
    corpus (>cap dated narrators) the cap was applied to the earliest-death set
    *before* the viewport filter, so a late viewport silently under-returned. This
    test FAILS against that code (the viewport filter never reaches Cypher, so the
    fake returns the early page and the late narrators are absent).
    """
    early = [_attested_narrator(f"early-{i}", 40 + i, 110 + i) for i in range(5)]
    late = [
        _attested_narrator("late-a", 220, 260),
        _attested_narrator("late-b", 222, 270),
        _attested_narrator("late-c", 224, 280),
    ]
    mock_neo4j.execute_read.side_effect = _fake_neo4j_viewport(early + late)

    resp = client.get("/api/v1/timeline/narrators?start_year=250&end_year=300&limit=3")
    assert resp.status_code == 200
    body = resp.json()
    ids = {e["narrator_id"] for e in body["entries"]}
    # The late-death narrators (which overlap the 250-300 viewport) are present ...
    assert ids == {"late-a", "late-b", "late-c"}
    # ... and none of the earliest-death narrators leaked through.
    assert not any(i.startswith("early-") for i in ids)


def test_timeline_narrators_truncated_when_viewport_set_exceeds_cap(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """``truncated`` is True when the cap clips the viewport-filtered set."""
    late = [_attested_narrator(f"late-{i}", 220 + i, 260 + i) for i in range(5)]
    mock_neo4j.execute_read.side_effect = _fake_neo4j_viewport(late)

    resp = client.get("/api/v1/timeline/narrators?start_year=250&end_year=300&limit=3")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["entries"]) == 3
    assert body["total"] == 3
    assert body["truncated"] is True


def test_timeline_narrators_not_truncated_when_within_cap(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """``truncated`` is False when the viewport-filtered set fits under the cap."""
    late = [_attested_narrator(f"late-{i}", 220 + i, 260 + i) for i in range(3)]
    mock_neo4j.execute_read.side_effect = _fake_neo4j_viewport(late)

    resp = client.get("/api/v1/timeline/narrators?start_year=250&end_year=300&limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["entries"]) == 3
    assert body["truncated"] is False


def test_timeline_narrators_passes_viewport_into_cypher(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """The viewport bounds are threaded into the Cypher params (so filtering
    happens in-query, before the LIMIT), and the LIMIT probes one past the cap."""
    mock_neo4j.execute_read.side_effect = [[]]
    resp = client.get("/api/v1/timeline/narrators?start_year=250&end_year=300&limit=7")
    assert resp.status_code == 200

    query, params = mock_neo4j.execute_read.call_args_list[0][0]
    assert params["start_year"] == 250
    assert params["end_year"] == 300
    # limit+1 probe for truncation detection.
    assert params["limit"] == 8
    # The window-overlap predicate lives in Cypher now, not Python.
    assert "window_end >= $start_year" in query
    assert "window_start <= $end_year" in query
