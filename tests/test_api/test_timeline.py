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
