"""Tests for collection endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

SAMPLE_COLLECTION = {
    "id": "col-001",
    "name_ar": "صحيح البخاري",
    "name_en": "Sahih al-Bukhari",
    "sect": "sunni",
}


def test_list_collections_empty(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/collections returns empty paginated response when no data."""
    mock_neo4j.execute_read.side_effect = [[{"total": 0}], []]
    resp = client.get("/api/v1/collections")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1


def test_list_collections_with_data(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/collections returns paginated collections from Neo4j."""
    mock_neo4j.execute_read.side_effect = [[{"total": 1}], [{"props": SAMPLE_COLLECTION}]]
    resp = client.get("/api/v1/collections")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "col-001"
    assert body["items"][0]["name_en"] == "Sahih al-Bukhari"
    assert body["total"] == 1


def test_get_collection_found(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/collections/{id} returns collection when found."""
    mock_neo4j.execute_read.return_value = [{"props": SAMPLE_COLLECTION}]
    resp = client.get("/api/v1/collections/col-001")
    assert resp.status_code == 200
    assert resp.json()["id"] == "col-001"


def test_list_collections_with_extra_and_missing_props(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """Collections with extra Neo4j props or missing optional fields don't 500."""
    props = {
        "id": "col:bukhari",
        "name_ar": "صحيح البخاري",
        "name_en": "Sahih al-Bukhari",
        "sect": "sunni",
        "source_corpus": "bukhari",  # extra field not in CollectionResponse
    }
    mock_neo4j.execute_read.side_effect = [[{"total": 1}], [{"props": props}]]
    resp = client.get("/api/v1/collections")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "col:bukhari"
    assert "source_corpus" not in body["items"][0]


def test_list_collections_null_sect(client: TestClient, mock_neo4j: MagicMock) -> None:
    """A collection node missing the sect property should not cause a 500."""
    props = {"id": "col:test", "name_ar": "اختبار", "name_en": "Test"}
    mock_neo4j.execute_read.side_effect = [[{"total": 1}], [{"props": props}]]
    resp = client.get("/api/v1/collections")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["sect"] == ""


def test_get_collection_not_found(client: TestClient) -> None:
    """GET /api/v1/collections/{id} returns 404 when not found."""
    resp = client.get("/api/v1/collections/nonexistent")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
