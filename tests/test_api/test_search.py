"""Tests for search endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
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
    # Raw Lucene scores (2.5 narrator, 1.8 hadith) pass through the saturating
    # transform ``score / (score + k)`` on the API side (ig#1070): bounded to
    # [0, 1) and relative order preserved, but the top hit is NOT pinned to 1.0.
    assert 0.0 < body["results"][0]["score"] < 1.0
    assert body["results"][0]["score"] > body["results"][1]["score"]
    assert body["results"][1]["type"] == "hadith"

    # Verify the full-text query was used (CALL db.index.fulltext)
    first_call_query = mock_neo4j.execute_read.call_args_list[0][0][0]
    assert "fulltext.queryNodes" in first_call_query
    # Verify a dedicated count query was issued
    count_query = mock_neo4j.execute_read.call_args_list[2][0][0]
    assert "count(" in count_query


def test_search_populates_facet_metadata(client: TestClient, mock_neo4j: MagicMock) -> None:
    """Results carry the facet metadata the search page filters on (#1036).

    Narrators get a derived ``century`` (from death year); hadiths get
    ``collection``, a normalized ``grade`` token, and ``topics``.
    """
    mock_neo4j.execute_read.side_effect = [
        # narrator full-text search — death_year_ah drives the century facet
        [
            {
                "id": "nar-1",
                "name_ar": "الزهري",
                "name_en": "al-Zuhri",
                "death_year_ah": 124,
                "score": 2.0,
            }
        ],
        # hadith full-text search — raw grade is normalized to its canonical token
        [
            {
                "id": "had-1",
                "matn_ar": "نص",
                "matn_en": "matn text",
                "score": 1.0,
                "collection_name": "Sahih al-Bukhari",
                "topic_tags": ["intentions"],
                "grade": "Sahih - Authentic",
            }
        ],
        [{"total": 1}],  # narrator count
        [{"total": 1}],  # hadith count
    ]
    resp = client.get("/api/v1/search?q=test")
    assert resp.status_code == 200
    results = resp.json()["results"]

    narrator = next(r for r in results if r["type"] == "narrator")
    assert narrator["century"] == 2  # 124 AH -> 2nd century
    assert narrator["collection"] is None
    assert narrator["topics"] == []

    hadith = next(r for r in results if r["type"] == "hadith")
    assert hadith["collection"] == "Sahih al-Bukhari"
    assert hadith["grade"] == "sahih"  # normalized from "Sahih - Authentic"
    # Raw tag "intentions" maps onto the canonical "akhlaq" topic (#1061).
    assert hadith["topics"] == ["akhlaq"]
    assert hadith["century"] is None


def test_search_facet_metadata_defaults_when_absent(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """Missing graph properties leave facet fields null/empty, not erroring (#1036)."""
    mock_neo4j.execute_read.side_effect = [
        [{"id": "nar-1", "name_ar": "x", "name_en": "n", "score": 1.0}],
        [{"id": "had-1", "matn_ar": "m", "matn_en": "h", "score": 1.0}],
        [{"total": 1}],
        [{"total": 1}],
    ]
    resp = client.get("/api/v1/search?q=test")
    assert resp.status_code == 200
    for r in resp.json()["results"]:
        assert r["century"] is None
        assert r["collection"] is None
        assert r["grade"] is None
        assert r["topics"] == []


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


def test_search_saturates_lucene_scores_to_unit_range(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """Full-text raw Lucene scores pass through the saturating transform (ig#1070).

    Relative ordering must be preserved: the narrator (raw 2.5) outscores the
    hadith (raw 1.8), so after the transform both must be in [0, 1) and the
    narrator score must remain higher — but unlike the old max-normalisation, the
    top hit is NOT forced to exactly 1.0.
    """
    mock_neo4j.execute_read.side_effect = [
        [{"id": "nar-1", "name_ar": "نص", "name_en": "narrator", "score": 2.5}],
        [{"id": "had-1", "matn_ar": "نص", "matn_en": "hadith text", "score": 1.8}],
        [{"total": 1}],
        [{"total": 1}],
    ]
    resp = client.get("/api/v1/search?q=test")
    assert resp.status_code == 200
    results = resp.json()["results"]

    narrator = next(r for r in results if r["type"] == "narrator")
    hadith = next(r for r in results if r["type"] == "hadith")

    # All scores must be within [0, 1) — no "250%" badges, none pinned to 100%.
    assert 0.0 <= narrator["score"] < 1.0
    assert 0.0 <= hadith["score"] < 1.0
    # Top (raw 2.5) hit is a moderate match, NOT 100% — that's the ig#1070 point.
    assert narrator["score"] < 0.99
    assert narrator["score"] == pytest.approx(2.5 / (2.5 + 5.0))
    # Relative order preserved: narrator still outscores hadith.
    assert narrator["score"] > hadith["score"]


def test_saturate_relevance_is_monotonic_and_bounded() -> None:
    """The pure transform is strictly monotonic and bounded to [0, 1) (ig#1070)."""
    from src.api.routes.search import saturate_relevance

    k = 5.0
    samples = [0.0, 0.1, 0.5, 1.0, 2.5, 10.0, 100.0, 1_000_000.0]
    mapped = [saturate_relevance(s, k) for s in samples]

    # Bounded: every output in [0, 1); even an enormous score never reaches 1.0.
    assert all(0.0 <= m < 1.0 for m in mapped)
    # Strictly monotonic increasing for strictly increasing positive inputs.
    assert all(a < b for a, b in zip(mapped[1:], mapped[2:]))
    # A zero / negative raw score floors to 0.0.
    assert saturate_relevance(0.0, k) == 0.0
    assert saturate_relevance(-3.0, k) == 0.0
    # Half-saturation: score == k maps to exactly 0.5.
    assert saturate_relevance(k, k) == pytest.approx(0.5)


def test_saturate_relevance_weak_top_hit_not_pinned_to_one() -> None:
    """A weak top hit reads as weak absolute confidence, not 100% (ig#1070).

    This is the core regression ig#1070 fixes: the old max-normalisation forced
    the single best result of every query to 1.0 regardless of match strength.
    """
    from src.api.routes.search import saturate_relevance

    # A weak BM25 score of 0.4 with default k=5.0 maps well below the sahih
    # (≥0.9) and warning (≥0.7) badge thresholds.
    weak = saturate_relevance(0.4, 5.0)
    assert weak < 0.7
    assert weak != pytest.approx(1.0)


def test_saturation_k_reads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """``k`` is sourced from env ``SEARCH_RELEVANCE_SATURATION_K`` (ig#1070).

    The default must be a positive, documented constant — not hard-wired — so it
    can be calibrated against real BM25 distributions without a code change.
    """
    from src.config import SearchSettings

    # Default is a sane positive constant (the provisional, calibration-pending k).
    assert SearchSettings().relevance_saturation_k > 0.0
    # ...and it is overridable from the environment.
    monkeypatch.setenv("SEARCH_RELEVANCE_SATURATION_K", "20.0")
    assert SearchSettings().relevance_saturation_k == pytest.approx(20.0)
    # A non-positive k is rejected (would break the transform's denominator).
    with pytest.raises(ValueError):
        SearchSettings(relevance_saturation_k=0.0)


def test_search_route_honours_configured_k(
    app: FastAPI, client: TestClient, mock_neo4j: MagicMock
) -> None:
    """The /search transform uses the configured ``k``, not a magic number (ig#1070).

    A larger ``k`` saturates more slowly, so the same raw score earns a lower
    badge percentage — the calibration knob the issue calls for.

    The route resolves ``k`` from its dedicated ``get_search_settings``
    dependency, so we override that dependency directly. This is deterministic
    regardless of test order (unlike mutating the cached singleton, which an
    earlier test may have already fixed at the default) — the very failure mode
    this guards against.
    """
    from src.api.routes import search as search_route
    from src.config import SearchSettings, Settings

    # Override the route's dedicated settings dependency by its own reference,
    # which is order-independent (it does not depend on whether other suites have
    # ``patch``ed ``src.config.get_settings``).
    app.dependency_overrides[search_route.get_search_settings] = lambda: Settings(
        search=SearchSettings(relevance_saturation_k=20.0)
    )
    try:
        mock_neo4j.execute_read.side_effect = [
            [{"id": "nar-1", "name_ar": "نص", "name_en": "narrator", "score": 2.5}],
            [],
            [{"total": 1}],
            [{"total": 0}],
        ]
        resp = client.get("/api/v1/search?q=test")
        assert resp.status_code == 200
        # 2.5 / (2.5 + 20.0) — markedly lower than the default-k mapping above.
        assert resp.json()["results"][0]["score"] == pytest.approx(2.5 / (2.5 + 20.0))
    finally:
        app.dependency_overrides.pop(search_route.get_search_settings, None)


def test_semantic_search_clamps_negative_score(client: TestClient, app: object) -> None:
    """Cosine similarity ``1 - distance`` can be negative; clamp to 0 (ig#1065)."""
    mock_pg = MagicMock()
    mock_pg.execute.side_effect = [
        [{"id": "had-1", "matn_ar": "نص", "matn_en": "hadith text", "score": -0.1}],
        [{"total": 1}],
    ]
    mock_pg.close.return_value = None

    from fastapi import FastAPI

    from src.api.deps import get_pg

    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_pg] = lambda: mock_pg

    resp = client.get("/api/v1/search/semantic?q=test")
    assert resp.status_code == 200
    body = resp.json()
    # Negative raw score must clamp to 0, never surface as a negative percentage.
    assert body["results"][0]["score"] == pytest.approx(0.0)

    del app.dependency_overrides[get_pg]


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


def test_semantic_search_different_queries_rank_differently(
    client: TestClient, app: object
) -> None:
    """Two different queries produce different embedding vectors, so pgvector
    ranks the same candidate hadiths in different orders for each (#1067).

    The deterministic HashingEmbedder guarantees "prayer in congregation" and
    "fasting in Ramadan" hash to distinct vectors — confirmed here by capturing
    the bound parameter each request passes to the ``<=>`` operator.  A live
    pgvector backend would therefore return different row orderings per query.

    Also covers the "novel query" criterion: neither string is stored in
    ``hadith_embeddings.text``, yet both calls return 200 — results are not
    gated on the query being a verbatim stored hadith.
    """
    mock_pg = MagicMock()
    mock_pg.execute.side_effect = [
        # data query for "prayer in congregation"
        [{"id": "had-1", "matn_ar": "نص", "matn_en": "hadith text a", "score": 0.8}],
        [{"total": 20}],  # count for "prayer in congregation"
        # data query for "fasting in Ramadan"
        [{"id": "had-1", "matn_ar": "نص", "matn_en": "hadith text a", "score": 0.4}],
        [{"total": 20}],  # count for "fasting in Ramadan"
    ]
    mock_pg.close.return_value = None

    from fastapi import FastAPI

    from src.api.deps import get_pg

    assert isinstance(app, FastAPI)
    app.dependency_overrides[get_pg] = lambda: mock_pg

    resp_a = client.get("/api/v1/search/semantic?q=prayer in congregation")
    resp_b = client.get("/api/v1/search/semantic?q=fasting in Ramadan")

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200

    # Each request issues 2 pg.execute calls: data query then count query.
    # Indices 0 and 2 are the data queries; their second positional arg is
    # (vec, vec, limit) — we capture the first element (the query vector).
    calls = mock_pg.execute.call_args_list
    _sql_prayer, params_prayer = calls[0].args
    _sql_fasting, params_fasting = calls[2].args
    vec_prayer = params_prayer[0]  # pgvector literal for "prayer in congregation"
    vec_fasting = params_fasting[0]  # pgvector literal for "fasting in Ramadan"

    # Distinct query texts → distinct hashing vectors → ORDER BY <=> evaluates
    # differently per query (real ranking diverges without a live db).
    assert vec_prayer != vec_fasting, (
        "Identical embedding vectors for different queries — "
        "query is not being embedded at runtime (#1067)"
    )
    # Neither param leaks the raw query string (would indicate the old exact-text
    # lookup bug is back).
    assert "prayer" not in vec_prayer
    assert "fasting" not in vec_fasting
    # Both are pgvector text literals (the %s::vector bound-param form).
    assert vec_prayer.startswith("[") and vec_prayer.endswith("]")
    assert vec_fasting.startswith("[") and vec_fasting.endswith("]")

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
