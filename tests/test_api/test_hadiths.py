"""Tests for hadith endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

SAMPLE_HADITH = {
    "id": "hdt:lk:abu_dawud:10:1574",
    "matn_ar": "إنما الأعمال بالنيات",
    "matn_en": "Actions are by intentions",
    "source_corpus": "lk",
    "collection_name": "abu_dawud",
}


def test_list_hadiths_empty(client: TestClient) -> None:
    """GET /api/v1/hadiths returns empty paginated response when no data."""
    resp = client.get("/api/v1/hadiths")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_hadiths_with_data(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/hadiths returns hadiths from Neo4j."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": SAMPLE_HADITH}],
    ]
    resp = client.get("/api/v1/hadiths")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "hdt:lk:abu_dawud:10:1574"
    assert body["items"][0]["display_title"] == "abu_dawud 10:1574"
    assert body["items"][0]["collection_name"] == "abu_dawud"


def test_list_hadiths_display_title_with_known_collection(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """Display title uses collection_name when available."""
    hadith = {
        **SAMPLE_HADITH,
        "collection_name": "Sunan Abu Dawud",
    }
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": hadith}],
    ]
    resp = client.get("/api/v1/hadiths")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["display_title"] == "Sunan Abu Dawud 10:1574"


def test_list_hadiths_filter_by_collection(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/hadiths?collection=X passes filter to query."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": SAMPLE_HADITH}],
    ]
    resp = client.get("/api/v1/hadiths?collection=abu_dawud")
    assert resp.status_code == 200
    # Verify that the query included the collection filter
    calls = mock_neo4j.execute_read.call_args_list
    count_query = calls[0][0][0]
    assert "collection_name" in count_query


def test_list_hadiths_filter_by_source_corpus(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/hadiths?source_corpus=lk passes filter to query."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": SAMPLE_HADITH}],
    ]
    resp = client.get("/api/v1/hadiths?source_corpus=lk")
    assert resp.status_code == 200
    calls = mock_neo4j.execute_read.call_args_list
    count_query = calls[0][0][0]
    assert "source_corpus" in count_query


def test_list_hadiths_text_search(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/hadiths?q=intentions passes text search filter."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": SAMPLE_HADITH}],
    ]
    resp = client.get("/api/v1/hadiths?q=intentions")
    assert resp.status_code == 200
    calls = mock_neo4j.execute_read.call_args_list
    count_query = calls[0][0][0]
    assert "toLower" in count_query


def test_get_hadith_found(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/hadiths/{id} returns hadith when found."""
    mock_neo4j.execute_read.return_value = [{"props": SAMPLE_HADITH}]
    resp = client.get("/api/v1/hadiths/hdt:lk:abu_dawud:10:1574")
    assert resp.status_code == 200
    assert resp.json()["id"] == "hdt:lk:abu_dawud:10:1574"
    assert resp.json()["matn_en"] == "Actions are by intentions"
    assert resp.json()["display_title"] is not None


def test_get_hadith_not_found(client: TestClient) -> None:
    """GET /api/v1/hadiths/{id} returns 404 when not found."""
    resp = client.get("/api/v1/hadiths/nonexistent")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
