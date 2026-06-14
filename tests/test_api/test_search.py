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


def test_search_limit_at_cap_is_accepted(client: TestClient, mock_neo4j: MagicMock) -> None:
    """limit at the endpoint cap (100) is accepted — the frontend results page
    requests this much, so the cap must cover it (#1025)."""
    mock_neo4j.execute_read.return_value = []
    resp = client.get("/api/v1/search?q=test&limit=100")
    assert resp.status_code == 200


def test_search_limit_over_cap_is_422(client: TestClient) -> None:
    """limit above the cap is rejected with 422 before any query runs. This is
    the failure the frontend hit when it asked for limit=200 (#1025)."""
    resp = client.get("/api/v1/search?q=test&limit=101")
    assert resp.status_code == 422


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


def test_semantic_search_embeds_query_at_runtime(client: TestClient, app: object) -> None:
    """The query is embedded into a pgvector literal, not matched by exact text.

    Regression for #1049: the old implementation looked the query up by
    ``WHERE text = %s``, so an arbitrary query returned nothing even with
    embeddings loaded. The endpoint must now pass an embedded *vector* to the
    ``<=>`` operator.
    """
    mock_pg = MagicMock()
    mock_pg.execute.side_effect = [
        [{"id": "had-1", "matn_ar": "نص", "matn_en": "ranked hadith", "score": 0.7}],
        [{"total": 12}],
    ]
    mock_pg.close.return_value = None

    from fastapi import FastAPI

    from src.api.deps import get_pg

    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_pg] = lambda: mock_pg

    resp = client.get("/api/v1/search/semantic?q=prayer in congregation&limit=5")
    assert resp.status_code == 200

    # First pg.execute is the ranked data query; its first bound param must be the
    # embedded query vector (a pgvector literal), never the raw query string.
    data_sql, data_params = mock_pg.execute.call_args_list[0].args
    vector_literal = data_params[0]
    assert vector_literal.startswith("[") and vector_literal.endswith("]")
    assert "prayer in congregation" not in str(data_params)
    # The cast `%s::vector` keeps the literal a bound parameter, never inline SQL.
    assert "%s::vector" in data_sql
    assert data_params[-1] == 5  # limit threaded through

    del app.dependency_overrides[get_pg]


def test_semantic_search_limit_over_cap_is_422(client: TestClient, app: object) -> None:
    """semantic limit above its cap (50) is rejected with 422 — the frontend
    results page must stay within this cap (#1025).

    The pg dependency is overridden with a mock so the assertion isolates the
    request-validation behaviour and never touches a real database (FastAPI
    resolves dependencies while validating params)."""
    mock_pg = MagicMock()
    mock_pg.close.return_value = None

    from fastapi import FastAPI

    from src.api.deps import get_pg

    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_pg] = lambda: mock_pg

    resp = client.get("/api/v1/search/semantic?q=test&limit=51")
    assert resp.status_code == 422
    # Validation rejects the request before the handler queries pgvector.
    mock_pg.execute.assert_not_called()

    del app.dependency_overrides[get_pg]


def test_semantic_search_limit_at_cap_is_accepted(client: TestClient, app: object) -> None:
    """semantic limit at its cap (50) is accepted (#1025)."""
    mock_pg = MagicMock()
    mock_pg.execute.side_effect = [[], [{"total": 0}]]
    mock_pg.close.return_value = None

    from fastapi import FastAPI

    from src.api.deps import get_pg

    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_pg] = lambda: mock_pg

    resp = client.get("/api/v1/search/semantic?q=test&limit=50")
    assert resp.status_code == 200

    del app.dependency_overrides[get_pg]
