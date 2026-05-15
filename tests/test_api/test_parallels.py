"""Tests for parallel hadith endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

SAMPLE_PAIR = {
    "a_id": "had-001",
    "a_corpus": "sunnah",
    "b_id": "had-002",
    "b_corpus": "shia",
    "similarity_score": 0.91,
    "variant_type": "wording",
    "cross_sect": True,
}

SAMPLE_PARALLEL = {
    "id": "had-002",
    "matn_ar": "نص مشابه",
    "matn_en": "a parallel narration",
    "source_corpus": "shia",
    "grade": "sahih",
    "similarity_score": 0.91,
    "variant_type": "wording",
    "cross_sect": True,
}


def test_list_parallels_empty(client: TestClient) -> None:
    """GET /api/v1/parallels returns an empty page when no parallel pairs exist."""
    resp = client.get("/api/v1/parallels")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1


def test_list_parallels_returns_pairs(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/parallels returns parallel pairs with similarity metadata."""
    mock_neo4j.execute_read.side_effect = [
        # count query
        [{"total": 1}],
        # data query
        [SAMPLE_PAIR],
    ]
    resp = client.get("/api/v1/parallels")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["hadith_a_id"] == "had-001"
    assert item["hadith_b_id"] == "had-002"
    assert item["similarity_score"] == 0.91
    assert item["cross_sect"] is True


def test_list_parallels_total_reflects_full_count(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """total comes from a dedicated COUNT query, not the page-limited item list."""
    mock_neo4j.execute_read.side_effect = [
        # count query over the full set
        [{"total": 175}],
        # page-limited data query
        [SAMPLE_PAIR],
    ]
    resp = client.get("/api/v1/parallels?limit=1")
    assert resp.status_code == 200
    body = resp.json()
    # total is the true count, not len(items) which is capped at limit
    assert body["total"] == 175
    assert len(body["items"]) == 1

    count_query = mock_neo4j.execute_read.call_args_list[0][0][0]
    assert "count(r)" in count_query


def test_list_parallels_pagination_skip(client: TestClient, mock_neo4j: MagicMock) -> None:
    """page/limit translate into the expected SKIP value on the data query."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 100}],
        [SAMPLE_PAIR],
    ]
    resp = client.get("/api/v1/parallels?page=3&limit=20")
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 3
    assert body["limit"] == 20

    data_params = mock_neo4j.execute_read.call_args_list[1][0][1]
    assert data_params["skip"] == 40
    assert data_params["limit"] == 20


def test_list_parallels_rejects_invalid_limit(client: TestClient) -> None:
    """GET /api/v1/parallels?limit=0 is rejected by the ge=1 bound."""
    resp = client.get("/api/v1/parallels?limit=0")
    assert resp.status_code == 422


def test_get_parallels_for_hadith(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/parallels/{hadith_id} returns parallels for an existing hadith."""
    mock_neo4j.execute_read.side_effect = [
        # existence check
        [{"id": "had-001"}],
        # parallels data query
        [SAMPLE_PARALLEL],
    ]
    resp = client.get("/api/v1/parallels/had-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hadith_id"] == "had-001"
    assert body["total"] == 1
    assert len(body["parallels"]) == 1
    assert body["parallels"][0]["id"] == "had-002"
    assert body["parallels"][0]["similarity_score"] == 0.91


def test_get_parallels_missing_hadith_404(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/parallels/{hadith_id} returns 404 when the hadith does not exist."""
    # existence check returns no rows
    mock_neo4j.execute_read.side_effect = [[]]
    resp = client.get("/api/v1/parallels/had-missing")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_get_parallels_empty_for_existing_hadith(client: TestClient, mock_neo4j: MagicMock) -> None:
    """An existing hadith with no PARALLEL_OF edges returns an empty parallels list."""
    mock_neo4j.execute_read.side_effect = [
        # existence check passes
        [{"id": "had-001"}],
        # no parallels
        [],
    ]
    resp = client.get("/api/v1/parallels/had-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hadith_id"] == "had-001"
    assert body["parallels"] == []
    assert body["total"] == 0


def test_get_parallels_pagination_skip(client: TestClient, mock_neo4j: MagicMock) -> None:
    """page/limit translate into the expected SKIP on the per-hadith parallels query."""
    mock_neo4j.execute_read.side_effect = [
        [{"id": "had-001"}],
        [SAMPLE_PARALLEL],
    ]
    resp = client.get("/api/v1/parallels/had-001?page=2&limit=5")
    assert resp.status_code == 200

    data_params = mock_neo4j.execute_read.call_args_list[1][0][1]
    assert data_params["id"] == "had-001"
    assert data_params["skip"] == 5
    assert data_params["limit"] == 5
