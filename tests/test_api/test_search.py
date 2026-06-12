"""Tests for search endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def test_search_fulltext_returns_results(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/search?q=test uses full-text index and returns results."""
    mock_neo4j.execute_read.side_effect = [
        # narrator full-text search
        [
            {
                "id": "nar-001",
                "name_ar": "اختبار",
                "name_en": "test narrator",
                "score": 2.5,
            }
        ],
        # hadith full-text search
        [
            {
                "id": "had-001",
                "matn_ar": "نص اختبار",
                "matn_en": "test hadith text",
                "score": 1.8,
            }
        ],
        # narrator count query
        [{"total": 7}],
        # hadith count query
        [{"total": 12}],
    ]
    resp = client.get("/api/v1/search?q=test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "test"
    # total reflects the full match count (7 + 12), not the page-limited
    # result list length (2)
    assert body["total"] == 19
    assert len(body["results"]) == 2
    assert body["results"][0]["type"] == "narrator"
    assert body["results"][0]["score"] == 2.5
    assert body["results"][1]["type"] == "hadith"

    # Verify the full-text query was used (CALL db.index.fulltext)
    first_call_query = mock_neo4j.execute_read.call_args_list[0][0][0]
    assert "fulltext.queryNodes" in first_call_query
    # Verify a dedicated count query was issued
    count_query = mock_neo4j.execute_read.call_args_list[2][0][0]
    assert "count(" in count_query


def test_search_total_exceeds_limit(client: TestClient, mock_neo4j: MagicMock) -> None:
    """total reflects the true match count even when results are capped at limit."""
    narrator_hits = [
        {"id": f"nar-{i}", "name_ar": "اختبار", "name_en": f"n{i}", "score": 1.0} for i in range(2)
    ]
    hadith_hits = [
        {"id": f"had-{i}", "matn_ar": "نص", "matn_en": f"h{i}", "score": 1.0} for i in range(2)
    ]
    mock_neo4j.execute_read.side_effect = [
        narrator_hits,
        hadith_hits,
        [{"total": 50}],  # narrator count
        [{"total": 130}],  # hadith count
    ]
    resp = client.get("/api/v1/search?q=test&limit=4")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 4
    assert body["total"] == 180


def test_search_falls_back_to_contains(client: TestClient, mock_neo4j: MagicMock) -> None:
    """When full-text index is unavailable, falls back to CONTAINS."""
    # narrator: fulltext raises, CONTAINS fallback succeeds
    # hadith: fulltext raises, CONTAINS fallback succeeds
    # narrator count: fulltext raises, CONTAINS count fallback succeeds
    # hadith count: fulltext raises, CONTAINS count fallback succeeds
    mock_neo4j.execute_read.side_effect = [
        Exception("No such index 'narrator_search'"),
        [{"id": "nar-001", "name_ar": "اختبار", "name_en": "fallback", "score": 1.0}],
        Exception("No such index 'hadith_search'"),
        [],
        Exception("No such index 'narrator_search'"),
        [{"total": 1}],
        Exception("No such index 'hadith_search'"),
        [{"total": 0}],
    ]
    resp = client.get("/api/v1/search?q=test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["title"] == "fallback"

    # Verify fallback query uses CONTAINS
    fallback_query = mock_neo4j.execute_read.call_args_list[1][0][0]
    assert "CONTAINS" in fallback_query


def test_search_empty_results(client: TestClient) -> None:
    """GET /api/v1/search?q=xyz returns empty results when nothing matches."""
    resp = client.get("/api/v1/search?q=xyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []


def test_search_missing_query_is_noop(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/search without q param is a clean no-op (200, empty), not 422."""
    resp = client.get("/api/v1/search")
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == ""
    assert body["total"] == 0
    assert body["results"] == []
    # Blank input must short-circuit before any Neo4j query.
    mock_neo4j.execute_read.assert_not_called()


def test_search_empty_query_is_noop(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/search?q= (explicit empty) is a clean no-op, not 422."""
    resp = client.get("/api/v1/search?q=")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []
    mock_neo4j.execute_read.assert_not_called()


def test_search_blank_query_is_noop(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/search?q=%20%20 (whitespace-only) is a clean no-op, not 422."""
    resp = client.get("/api/v1/search?q=%20%20")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["results"] == []
    mock_neo4j.execute_read.assert_not_called()


def test_semantic_search_returns_503_when_pg_unavailable(client: TestClient, app: object) -> None:
    """GET /api/v1/search/semantic returns 503 when pgvector is not available."""
    from fastapi import FastAPI

    from src.api.deps import get_pg

    mock_pg = MagicMock()
    mock_pg.execute.side_effect = Exception("relation does not exist")
    mock_pg.close.return_value = None

    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_pg] = lambda: mock_pg

    resp = client.get("/api/v1/search/semantic?q=test")
    assert resp.status_code == 503
    body = resp.json()
    assert "not yet available" in body["detail"].lower()

    del app.dependency_overrides[get_pg]


def test_semantic_search_returns_results_when_pg_available(client: TestClient, app: object) -> None:
    """GET /api/v1/search/semantic returns results when pgvector is wired up."""
    mock_pg = MagicMock()
    mock_pg.execute.side_effect = [
        # similarity-ranked data query (capped at limit)
        [
            {
                "id": "had-001",
                "matn_ar": "نص اختبار",
                "matn_en": "test semantic hadith",
                "score": 0.92,
            },
        ],
        # dedicated count query over the full candidate set
        [{"total": 84}],
    ]
    mock_pg.close.return_value = None

    from fastapi import FastAPI

    from src.api.deps import get_pg

    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_pg] = lambda: mock_pg

    resp = client.get("/api/v1/search/semantic?q=test")
    assert resp.status_code == 200
    body = resp.json()
    # total reflects the full candidate set, not the page-limited result list
    assert body["total"] == 84
    assert len(body["results"]) == 1
    assert body["results"][0]["type"] == "hadith"
    assert body["results"][0]["score"] == 0.92

    # Clean up override
    del app.dependency_overrides[get_pg]
