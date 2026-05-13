"""Tests for search endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from tests.factories import make_hadith_search_hit, make_narrator_search_hit


def test_search_fulltext_returns_results(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/search?q=test uses full-text index and returns results."""
    mock_neo4j.execute_read.side_effect = [
        # narrator full-text search
        [make_narrator_search_hit()],
        # hadith full-text search
        [make_hadith_search_hit()],
    ]
    resp = client.get("/api/v1/search?q=test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "test"
    assert body["total"] == 2
    assert body["results"][0]["type"] == "narrator"
    assert body["results"][0]["score"] == 2.5
    assert body["results"][1]["type"] == "hadith"

    # Verify the full-text query was used (CALL db.index.fulltext)
    first_call_query = mock_neo4j.execute_read.call_args_list[0][0][0]
    assert "fulltext.queryNodes" in first_call_query


def test_search_falls_back_to_contains(client: TestClient, mock_neo4j: MagicMock) -> None:
    """When full-text index is unavailable, falls back to CONTAINS."""
    # First call (fulltext) raises, second call (CONTAINS fallback) succeeds,
    # third call (hadith fulltext) raises, fourth call (hadith fallback) succeeds
    mock_neo4j.execute_read.side_effect = [
        Exception("No such index 'narrator_search'"),
        [make_narrator_search_hit(name_en="fallback", score=1.0)],
        Exception("No such index 'hadith_search'"),
        [],
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


def test_search_requires_query(client: TestClient) -> None:
    """GET /api/v1/search without q param returns 422."""
    resp = client.get("/api/v1/search")
    assert resp.status_code == 422


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
    mock_pg.execute.return_value = [
        make_hadith_search_hit(matn_en="test semantic hadith", score=0.92),
    ]
    mock_pg.close.return_value = None

    from fastapi import FastAPI

    from src.api.deps import get_pg

    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_pg] = lambda: mock_pg

    resp = client.get("/api/v1/search/semantic?q=test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["results"][0]["type"] == "hadith"
    assert body["results"][0]["score"] == 0.92

    # Clean up override
    del app.dependency_overrides[get_pg]
