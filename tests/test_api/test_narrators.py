"""Tests for narrator endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

SAMPLE_NARRATOR = {
    "id": "nar-001",
    "name_ar": "\u0623\u0628\u0648 \u0647\u0631\u064a\u0631\u0629",
    "name_en": "Abu Hurayra",
    "generation": "companion",
    "gender": "male",
    "sect_affiliation": "sunni",
    "trustworthiness_consensus": "thiqah",
}

# A narrator node carrying only the always-present fields — most real loaded
# narrators lack name_en / generation / gender / sect / trustworthiness. Before
# #1024 these absent required fields raised a Pydantic ValidationError → 500.
SPARSE_NARRATOR = {
    "id": "nar-sparse",
    "name_ar": "فلان بن فلان",
}


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
        [{"props": SAMPLE_NARRATOR}],
    ]
    resp = client.get("/api/v1/narrators")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "nar-001"
    assert body["items"][0]["name_en"] == "Abu Hurayra"


def test_list_narrators_sparse_node(client: TestClient, mock_neo4j: MagicMock) -> None:
    """A narrator missing the sparse biographical fields serializes as 200, not 500 (#1024)."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": SPARSE_NARRATOR}],
    ]
    resp = client.get("/api/v1/narrators")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == "nar-sparse"
    # The absent fields come back as null rather than raising a validation error.
    assert item["name_en"] is None
    assert item["generation"] is None
    assert item["gender"] is None
    assert item["sect_affiliation"] is None
    assert item["trustworthiness_consensus"] is None


def test_list_narrators_pagination(client: TestClient, mock_neo4j: MagicMock) -> None:
    """Pagination params are forwarded correctly."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 50}],
        [{"props": SAMPLE_NARRATOR}],
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
            "rows": [{"props": SAMPLE_NARRATOR}],
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
            "rows": [{"props": SAMPLE_NARRATOR}],
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


def test_list_narrators_search_falls_back_to_contains(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """When ``narrator_search`` is absent, search degrades to CONTAINS (no 500)."""
    # First call (fulltext) raises as Neo4j does for a missing index;
    # second call (CONTAINS fallback) succeeds.
    mock_neo4j.execute_read.side_effect = [
        Exception("There is no such fulltext schema index: narrator_search"),
        [{"total": 1, "rows": [{"props": SAMPLE_NARRATOR}]}],
    ]
    resp = client.get("/api/v1/narrators?q=Abu")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["name_en"] == "Abu Hurayra"

    # Fulltext attempted first, then the CONTAINS fallback.
    assert mock_neo4j.execute_read.call_count == 2
    fallback_query = mock_neo4j.execute_read.call_args_list[1][0][0]
    assert "CONTAINS" in fallback_query
    assert "fulltext.queryNodes" not in fallback_query
    # Fallback matches on the raw query, not the Lucene-quoted phrase.
    assert mock_neo4j.execute_read.call_args_list[1][0][1]["q"] == "Abu"


def test_list_narrators_search_fallback_empty_not_500(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """Missing index + no CONTAINS matches yields an empty 200, never a 500."""
    mock_neo4j.execute_read.side_effect = [
        Exception("There is no such fulltext schema index: narrator_search"),
        [{"total": 0, "rows": []}],
    ]
    resp = client.get("/api/v1/narrators?q=Nobody")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_get_narrator_found(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/narrators/{id} returns narrator when found."""
    mock_neo4j.execute_read.return_value = [{"props": SAMPLE_NARRATOR}]
    resp = client.get("/api/v1/narrators/nar-001")
    assert resp.status_code == 200
    assert resp.json()["id"] == "nar-001"


def test_get_narrator_not_found(client: TestClient) -> None:
    """GET /api/v1/narrators/{id} returns 404 when not found."""
    resp = client.get("/api/v1/narrators/nonexistent")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
