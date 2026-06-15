"""Tests for parallel hadith endpoints.

Browse Parallels must span every sect combination (sunni-sunni, shia-shia, and
sunni-shia); ``cross_sect`` is an optional facet, not a mandatory filter (#964).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from .routes import PARALLELS

# An intra-sect (sunni-sunni) pair and a cross-sect (sunni-shia) pair, proving the
# Browse feed is not restricted to cross-sect pairings.
INTRA_PAIR = {
    "a_id": "hdt:sunni:bukhari:1:1",
    "a_corpus": "bukhari",
    "a_collection": "Sahih al-Bukhari",
    "a_matn_en": "Actions are but by intentions.",
    "a_matn_ar": "إنما الأعمال بالنيات",
    "b_id": "hdt:sunni:muslim:1:1",
    "b_corpus": "muslim",
    "b_collection": "Sahih Muslim",
    "b_matn_en": "Deeds are by intentions.",
    "b_matn_ar": "الأعمال بالنية",
    "similarity_score": 0.97,
    "variant_type": "verbatim",
    "cross_sect": False,
}
CROSS_PAIR = {
    "a_id": "hdt:sunni:bukhari:2:9",
    "a_corpus": "bukhari",
    "a_collection": "Sahih al-Bukhari",
    "a_matn_en": None,
    "a_matn_ar": None,
    "b_id": "hdt:shia:kafi:5",
    "b_corpus": "kafi",
    "b_collection": "Al-Kafi",
    "b_matn_en": None,
    "b_matn_ar": None,
    "similarity_score": 0.88,
    "variant_type": "close_paraphrase",
    "cross_sect": True,
}


def test_list_parallels_empty(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /parallels returns an empty paginated response when no edges exist."""
    mock_neo4j.execute_read.side_effect = [[{"total": 0}], []]
    resp = client.get(PARALLELS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1


def test_list_parallels_spans_both_sects(client: TestClient, mock_neo4j: MagicMock) -> None:
    """By default the Browse feed returns intra-sect AND cross-sect pairs (#964)."""
    mock_neo4j.execute_read.side_effect = [[{"total": 2}], [INTRA_PAIR, CROSS_PAIR]]
    resp = client.get(PARALLELS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert {p["cross_sect"] for p in body["items"]} == {False, True}
    intra = next(p for p in body["items"] if not p["cross_sect"])
    assert intra["hadith_a_id"] == "hdt:sunni:bukhari:1:1"
    assert intra["hadith_b_corpus"] == "muslim"


def test_list_parallels_enriches_rows_with_title_and_snippet(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """Each Browse row carries a human-readable title and a matn preview (#1037)."""
    mock_neo4j.execute_read.side_effect = [[{"total": 2}], [INTRA_PAIR, CROSS_PAIR]]
    resp = client.get(PARALLELS)
    assert resp.status_code == 200
    intra = next(p for p in resp.json()["items"] if not p["cross_sect"])
    # Title derived from collection_name + the book:hadith tail of the ID.
    assert intra["hadith_a_title"] == "Sahih al-Bukhari 1:1"
    assert intra["hadith_b_title"] == "Sahih Muslim 1:1"
    # Snippet prefers the English translation.
    assert intra["hadith_a_snippet"] == "Actions are but by intentions."

    # When a hadith has neither translation, the snippet is null (title-only row).
    cross = next(p for p in resp.json()["items"] if p["cross_sect"])
    assert cross["hadith_a_snippet"] is None
    assert cross["hadith_a_title"] == "Sahih al-Bukhari 2:9"


def test_list_parallels_truncates_long_snippet(client: TestClient, mock_neo4j: MagicMock) -> None:
    """A long matn is clipped to a single-line preview with an ellipsis (#1037)."""
    long_pair = {
        **INTRA_PAIR,
        "a_matn_en": "word " * 80,  # ~400 chars
    }
    mock_neo4j.execute_read.side_effect = [[{"total": 1}], [long_pair]]
    resp = client.get(PARALLELS)
    snippet = resp.json()["items"][0]["hadith_a_snippet"]
    assert snippet is not None
    assert snippet.endswith("…")
    assert len(snippet) <= 141  # 140 chars + ellipsis


def test_list_parallels_no_facet_omits_where_clause(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """Without the cross_sect facet, no cross_sect predicate is sent to Neo4j."""
    mock_neo4j.execute_read.side_effect = [[{"total": 0}], []]
    client.get(PARALLELS)
    count_query = mock_neo4j.execute_read.call_args_list[0].args[0]
    count_params = mock_neo4j.execute_read.call_args_list[0].args[1]
    assert "r.cross_sect" not in count_query
    assert "cross_sect" not in count_params


def test_list_parallels_cross_sect_true_filters(client: TestClient, mock_neo4j: MagicMock) -> None:
    """cross_sect=true adds a WHERE predicate binding cross_sect to True."""
    mock_neo4j.execute_read.side_effect = [[{"total": 1}], [CROSS_PAIR]]
    resp = client.get(f"{PARALLELS}?cross_sect=true")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["cross_sect"] is True
    count_query = mock_neo4j.execute_read.call_args_list[0].args[0]
    count_params = mock_neo4j.execute_read.call_args_list[0].args[1]
    assert "WHERE r.cross_sect = $cross_sect" in count_query
    assert count_params["cross_sect"] is True


def test_list_parallels_cross_sect_false_filters(client: TestClient, mock_neo4j: MagicMock) -> None:
    """cross_sect=false restricts to intra-sect pairs."""
    mock_neo4j.execute_read.side_effect = [[{"total": 1}], [INTRA_PAIR]]
    resp = client.get(f"{PARALLELS}?cross_sect=false")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["cross_sect"] is False
    data_params = mock_neo4j.execute_read.call_args_list[1].args[1]
    assert data_params["cross_sect"] is False


def test_get_parallels_not_found(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /parallels/{id} returns 404 when the hadith does not exist."""
    mock_neo4j.execute_read.side_effect = [[]]
    resp = client.get(f"{PARALLELS}/hadith:missing:1")
    assert resp.status_code == 404


def test_get_parallels_found_spans_sects(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /parallels/{id} returns parallels regardless of sect pairing."""
    mock_neo4j.execute_read.side_effect = [
        [{"id": "hadith:bukhari:1"}],  # hadith exists
        [
            {
                "id": "hadith:muslim:1",
                "matn_ar": "إنما الأعمال بالنيات",
                "matn_en": "Actions are by intentions.",
                "source_corpus": "muslim",
                "grade": "sahih",
                "similarity_score": 0.97,
                "variant_type": "verbatim",
                "cross_sect": False,
            }
        ],
    ]
    resp = client.get(f"{PARALLELS}/hadith:bukhari:1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["parallels"][0]["cross_sect"] is False
