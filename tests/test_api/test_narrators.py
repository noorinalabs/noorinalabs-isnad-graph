"""Tests for narrator endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from tests.factories import make_narrator_row


def test_list_narrators_empty(client: TestClient) -> None:
    """GET /api/v1/narrators returns empty paginated response when no data."""
    resp = client.get("/api/v1/narrators")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["limit"] == 20


def test_list_narrators_with_data(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/narrators returns narrators from Neo4j."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": make_narrator_row()}],
    ]
    resp = client.get("/api/v1/narrators")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "nar-001"
    assert body["items"][0]["name_en"] == "Abu Hurayra"


def test_list_narrators_pagination(client: TestClient, mock_neo4j: MagicMock) -> None:
    """Pagination params are forwarded correctly."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 50}],
        [{"props": make_narrator_row()}],
    ]
    resp = client.get("/api/v1/narrators?page=3&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 3
    assert body["limit"] == 10


def test_list_narrators_fulltext_search(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/narrators?q=... uses single fulltext query for count and results."""
    mock_neo4j.execute_read.return_value = [
        {
            "total": 1,
            "rows": [{"props": make_narrator_row()}],
        }
    ]
    resp = client.get("/api/v1/narrators?q=Abu")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["name_en"] == "Abu Hurayra"

    # Verify only a single execute_read call (no duplicate fulltext query)
    assert mock_neo4j.execute_read.call_count == 1
    query = mock_neo4j.execute_read.call_args[0][0]
    assert "fulltext.queryNodes" in query
    assert "size(all_rows)" in query


def test_list_narrators_fulltext_search_pagination(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """Fulltext search paginates correctly with a single query."""
    mock_neo4j.execute_read.return_value = [
        {
            "total": 25,
            "rows": [{"props": make_narrator_row()}],
        }
    ]
    resp = client.get("/api/v1/narrators?q=Abu&page=2&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 25
    assert body["page"] == 2
    assert body["limit"] == 10

    # Single query execution
    assert mock_neo4j.execute_read.call_count == 1
    params = mock_neo4j.execute_read.call_args[0][1]
    assert params["skip"] == 10
    assert params["limit"] == 10


def test_get_narrator_found(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/narrators/{id} returns narrator when found."""
    mock_neo4j.execute_read.return_value = [{"props": make_narrator_row()}]
    resp = client.get("/api/v1/narrators/nar-001")
    assert resp.status_code == 200
    assert resp.json()["id"] == "nar-001"


def test_get_narrator_not_found(client: TestClient) -> None:
    """GET /api/v1/narrators/{id} returns 404 when not found."""
    resp = client.get("/api/v1/narrators/nonexistent")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
