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


def test_get_hadith_facets_empty(client: TestClient) -> None:
    """GET /api/v1/hadiths/facets returns empty list when no data."""
    resp = client.get("/api/v1/hadiths/facets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_corpus"] == []


def test_get_hadith_facets_with_data(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/hadiths/facets returns distinct corpus + normalized grade values."""
    mock_neo4j.execute_read.side_effect = [
        # First call: corpus facets.
        [{"corpus": "lk"}, {"corpus": "sunnah"}, {"corpus": "thaqalayn"}],
        # Second call: raw free-text grades off Grading nodes.
        [
            {"grade": "Sahih - Authentic"},
            {"grade": "Sahih-Authentic"},
            {"grade": "Hasan Sahih"},
            {"grade": "Da'if in chain"},
            {"grade": "totally unknown"},
        ],
    ]
    resp = client.get("/api/v1/hadiths/facets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_corpus"] == ["lk", "sunnah", "thaqalayn"]
    # Distinct normalized tokens, sorted; "Sahih - Authentic"/"Sahih-Authentic"
    # collapse to one, and the unrecognized value is dropped.
    assert body["grades"] == ["daif", "hasan_sahih", "sahih"]


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


def test_list_hadiths_filter_by_narrator_in_isnad(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """GET /api/v1/hadiths?narrator=X filters to hadiths whose isnad contains X (#1050)."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": SAMPLE_HADITH}],
    ]
    resp = client.get("/api/v1/hadiths?narrator=nar:az-zuhri-0001")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    calls = mock_neo4j.execute_read.call_args_list
    count_query, count_params = calls[0][0][0], calls[0][0][1]
    # Membership = direct NARRATED ∪ per-hadith TRANSMITTED_TO (edge-keyed), and
    # must NOT depend on nonexistent Chain nodes (#1032 / #1050).
    assert "NARRATED" in count_query
    assert "TRANSMITTED_TO" in count_query
    assert "t.hadith_id = h.id" in count_query
    assert ":Chain" not in count_query
    assert count_params["narrator"] == "nar:az-zuhri-0001"


def test_list_hadiths_no_narrator_filter_omits_isnad_subquery(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """Without ?narrator the query stays a plain scan (no isnad subquery)."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": SAMPLE_HADITH}],
    ]
    resp = client.get("/api/v1/hadiths")
    assert resp.status_code == 200
    count_query = mock_neo4j.execute_read.call_args_list[0][0][0]
    assert "TRANSMITTED_TO" not in count_query


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


# --- ig#1048: grade is read via GRADED_BY traversal, not a flat property -------
#
# These fixtures deliberately do NOT set grade_composite on the Hadith props
# (matching production, where 0/34,028 hadiths carry it); the grade arrives as a
# separate row column from the OPTIONAL MATCH (h)-[:GRADED_BY]->(g) traversal.


def test_get_hadith_returns_traversed_grade(client: TestClient, mock_neo4j: MagicMock) -> None:
    """Detail surfaces the raw GRADED_BY grade and its normalized token."""
    mock_neo4j.execute_read.return_value = [{"props": SAMPLE_HADITH, "grade": "Sahih - Authentic"}]
    resp = client.get("/api/v1/hadiths/hdt:lk:abu_dawud:10:1574")
    assert resp.status_code == 200
    body = resp.json()
    assert body["grade_composite"] == "Sahih - Authentic"  # raw text for display
    assert body["grade_normalized"] == "sahih"  # canonical token for colour
    # The query must traverse GRADED_BY (the bug was that it never did).
    query = mock_neo4j.execute_read.call_args_list[0][0][0]
    assert "GRADED_BY" in query


def test_get_hadith_ungraded_has_null_grade(client: TestClient, mock_neo4j: MagicMock) -> None:
    """A hadith with no Grading node returns null grade fields, not an error."""
    mock_neo4j.execute_read.return_value = [{"props": SAMPLE_HADITH, "grade": None}]
    resp = client.get("/api/v1/hadiths/hdt:lk:abu_dawud:10:1574")
    assert resp.status_code == 200
    body = resp.json()
    assert body["grade_composite"] is None
    assert body["grade_normalized"] is None


def test_list_hadiths_returns_traversed_grade(client: TestClient, mock_neo4j: MagicMock) -> None:
    """List surfaces the GRADED_BY grade per item and traverses in both queries."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": SAMPLE_HADITH, "grade": "Hasan Sahih"}],
    ]
    resp = client.get("/api/v1/hadiths")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["grade_composite"] == "Hasan Sahih"
    assert item["grade_normalized"] == "hasan_sahih"
    count_query, data_query = (c[0][0] for c in mock_neo4j.execute_read.call_args_list)
    assert "GRADED_BY" in count_query
    assert "GRADED_BY" in data_query


def test_list_hadiths_filter_by_grade_is_real(client: TestClient, mock_neo4j: MagicMock) -> None:
    """The grade filter builds a predicate over the traversed grade (not a no-op)."""
    mock_neo4j.execute_read.side_effect = [
        [{"total": 1}],
        [{"props": SAMPLE_HADITH, "grade": "Sahih - Authentic"}],
    ]
    resp = client.get("/api/v1/hadiths?grade=sahih")
    assert resp.status_code == 200
    count_call = mock_neo4j.execute_read.call_args_list[0]
    count_query, params = count_call[0][0], count_call[0][1]
    # No longer the broken `h.grade_composite = $grade` flat-property comparison.
    assert "h.grade_composite = $grade" not in count_query
    # Filters against the coalesced traversed grade.
    assert "coalesce(g.grade" in count_query
    assert "GRADED_BY" in count_query
    # Keyword params for the sahih predicate are bound.
    assert any("sahih" in v for v in params.values() if isinstance(v, list))
