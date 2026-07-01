"""Tests for hadith endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.api.routes.hadiths import DEFAULT_ASSUMED_LIFESPAN_AH, derive_hadith_dating
from src.utils.grades import GRADE_TOKENS

SAMPLE_HADITH = {
    "id": "hdt:lk:abu_dawud:10:1574",
    "matn_ar": "إنما الأعمال بالنيات",
    "matn_en": "Actions are by intentions",
    "source_corpus": "lk",
    "collection_name": "abu_dawud",
}


def test_get_hadith_facets_empty(client: TestClient) -> None:
    """Corpus facet is empty with no data, but the grade vocabulary is corpus-independent."""
    resp = client.get("/api/v1/hadiths/facets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_corpus"] == []
    # The grade facet exposes the full canonical vocabulary regardless of whether
    # any hadiths are loaded — it no longer collapses to empty on a sparse corpus
    # (#1062), so every valid grade stays reachable as a filter.
    assert body["grades"] == sorted(GRADE_TOKENS)
    # The canonical topic vocabulary is always present (stable facet), with zero
    # counts and a zero uncategorized bucket when there are no hadiths (#1061).
    values = [t["value"] for t in body["topics"]]
    assert values == [
        "aqidah",
        "ibadah",
        "fiqh",
        "akhlaq",
        "quran",
        "sira",
        "knowledge",
        "eschatology",
        "uncategorized",
    ]
    assert all(t["count"] == 0 for t in body["topics"])


def test_get_hadith_facets_with_data(client: TestClient, mock_neo4j: MagicMock) -> None:
    """Corpus facets from data; grade facet = full canonical vocab; topic facet aggregated."""
    # Grades are sourced from the canonical enum (#1062), so the only DB reads are
    # the corpus query and the per-hadith topic_tags scan (#1061).
    mock_neo4j.execute_read.side_effect = [
        # First call: corpus facets.
        [{"corpus": "lk"}, {"corpus": "sunnah"}, {"corpus": "thaqalayn"}],
        # Second call: per-hadith topic_tags for the canonical topic facet.
        [
            {"topic_tags": ["intentions", "prayer"]},  # akhlaq + ibadah
            {"topic_tags": ["inheritance"]},  # fiqh
            {"topic_tags": ["something obscure"]},  # uncategorized (no match)
            {"topic_tags": []},  # uncategorized (no tags)
            {"topic_tags": None},  # uncategorized (missing property)
        ],
    ]
    resp = client.get("/api/v1/hadiths/facets")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_corpus"] == ["lk", "sunnah", "thaqalayn"]
    # Grade facet = full canonical vocabulary (#1062); grades a sparse corpus used
    # to hide are now facetable — see test_utils/test_grades.py for the predicate proof.
    assert body["grades"] == sorted(GRADE_TOKENS)
    for previously_unreachable in ("munkar", "shadh", "hasan_sahih"):
        assert previously_unreachable in body["grades"]
    # Topic facet: counts keyed by canonical token, incl. the uncategorized bucket (#1061).
    counts = {t["value"]: t["count"] for t in body["topics"]}
    assert counts["akhlaq"] == 1
    assert counts["ibadah"] == 1
    assert counts["fiqh"] == 1
    assert counts["uncategorized"] == 3  # obscure tag + empty + missing
    # Topics with no documents still appear (stable vocabulary).
    assert counts["eschatology"] == 0
    # Every bucket carries a human-readable label.
    assert all(t["label"] for t in body["topics"])


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


# --- Chain-derived dating (ig#1042) ---------------------------------------

# A seeded isnad chain: Companion (death-attested) -> Successor -> Collector.
# ``nar:`` ids + AH death years mirror the real narrator-date contract (ig#1039).
_ABU_HURAYRA = {
    "id": "nar:abu-hurayra",
    "name_ar": "\u0623\u0628\u0648 \u0647\u0631\u064a\u0631\u0629",
    "name_en": "Abu Hurayra",
    "death_year_ah": 58,
}
_AL_ZUHRI = {
    "id": "nar:al-zuhri",
    "name_ar": "\u0627\u0644\u0632\u0647\u0631\u064a",
    "name_en": "al-Zuhri",
    "death_year_ah": 124,
}
_MALIK = {
    "id": "nar:malik",
    "name_ar": "\u0645\u0627\u0644\u0643",
    "name_en": "Malik ibn Anas",
    "death_year_ah": 179,
}


def test_derive_hadith_dating_terminus_over_seeded_chain() -> None:
    """Termini are anchored on the earliest/latest narrator death across the chain.

    Fail-on-pre-fix: before ig#1042 there was no derivation at all. With the three
    death-attested narrators the window spans the earliest death (post-quem 58) to
    the latest death (ante-quem 179); span = 121; all dated -> high confidence.
    """
    result = derive_hadith_dating("hdt:lk:malik:1:1", [_AL_ZUHRI, _MALIK, _ABU_HURAYRA])
    assert result.terminus_post_quem_ah == 58
    assert result.terminus_ante_quem_ah == 179
    assert result.chain_span_ah == 121
    assert result.confidence == "high"
    assert result.chain_narrator_count == 3
    assert result.dated_narrator_count == 3
    assert result.earliest_narrator is not None
    assert result.earliest_narrator.narrator_id == "nar:abu-hurayra"
    assert result.latest_narrator is not None
    assert result.latest_narrator.narrator_id == "nar:malik"
    assert result.assumed_lifespan_ah == DEFAULT_ASSUMED_LIFESPAN_AH


def test_derive_hadith_dating_prefers_resolved_outer_bounds() -> None:
    """When ig#1039 ``*_latest`` bounds are present the window widens to them."""
    narrator = {
        "id": "nar:x",
        "death_year_ah": 150,
        "death_year_ah_latest": 158,
        "birth_year_ah": 80,
        "birth_year_ah_earliest": 72,
    }
    result = derive_hadith_dating("hdt:x", [narrator])
    # single dated narrator -> point window at the (widened) death bound
    assert result.terminus_ante_quem_ah == 158
    assert result.terminus_post_quem_ah == 158


def test_derive_hadith_dating_estimated_bound_is_medium() -> None:
    """A bounding window that rests on an assumed-lifespan estimate caps at medium."""
    birth_only = {"id": "nar:birth-only", "birth_year_ah": 120}  # window [120, 200], estimated
    result = derive_hadith_dating("hdt:x", [_ABU_HURAYRA, birth_only])
    assert result.terminus_post_quem_ah == 58
    assert result.terminus_ante_quem_ah == 200  # 120 + 80 assumed lifespan
    assert result.latest_narrator is not None
    assert result.latest_narrator.estimated is True
    assert result.confidence == "medium"


def test_derive_hadith_dating_single_dated_is_low() -> None:
    """One dated narrator collapses the span to a point -> low confidence."""
    undated = {"id": "nar:undated"}
    result = derive_hadith_dating("hdt:x", [_MALIK, undated])
    assert result.terminus_post_quem_ah == 179
    assert result.terminus_ante_quem_ah == 179
    assert result.chain_span_ah == 0
    assert result.dated_narrator_count == 1
    assert result.confidence == "low"


def test_derive_hadith_dating_insufficient_data_no_500() -> None:
    """An undated chain yields a null window with insufficient_data, not an error."""
    result = derive_hadith_dating("hdt:x", [{"id": "nar:a"}, {"id": "nar:b"}])
    assert result.terminus_post_quem_ah is None
    assert result.terminus_ante_quem_ah is None
    assert result.chain_span_ah is None
    assert result.confidence == "insufficient_data"
    assert result.chain_narrator_count == 2
    assert result.dated_narrator_count == 0
    assert "Insufficient data" in result.note


def test_get_hadith_dating_endpoint_over_seeded_chain(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """GET /hadiths/{id}/dating returns the chain-derived window (200)."""
    mock_neo4j.execute_read.side_effect = [
        [{"id": "hdt:lk:malik:1:1"}],  # exists check
        [_ABU_HURAYRA, _AL_ZUHRI, _MALIK],  # chain narrators
    ]
    resp = client.get("/api/v1/hadiths/hdt:lk:malik:1:1/dating")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hadith_id"] == "hdt:lk:malik:1:1"
    assert body["terminus_post_quem_ah"] == 58
    assert body["terminus_ante_quem_ah"] == 179
    assert body["chain_span_ah"] == 121
    assert body["confidence"] == "high"
    assert body["latest_narrator"]["narrator_id"] == "nar:malik"
    # The chain is reconstructed from edges, never nonexistent Chain nodes (#1032).
    chain_query = mock_neo4j.execute_read.call_args_list[1][0][0]
    assert "TRANSMITTED_TO" in chain_query
    assert "NARRATED" in chain_query
    assert ":Chain" not in chain_query


def test_get_hadith_dating_endpoint_undated_chain_is_graceful(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """A hadith whose chain carries no dates returns insufficient_data, not a 500."""
    mock_neo4j.execute_read.side_effect = [
        [{"id": "hdt:x"}],
        [{"id": "nar:a"}, {"id": "nar:b"}],
    ]
    resp = client.get("/api/v1/hadiths/hdt:x/dating")
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] == "insufficient_data"
    assert body["terminus_ante_quem_ah"] is None


def test_get_hadith_dating_endpoint_404_when_missing(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """A missing hadith 404s (the dating window is never fabricated for a non-hadith)."""
    mock_neo4j.execute_read.side_effect = [[]]  # exists check empty
    resp = client.get("/api/v1/hadiths/hdt:nope/dating")
    assert resp.status_code == 404
