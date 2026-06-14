"""Tests for graph traversal endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

# Production-shaped ids: canonical narrator ids are `nar:<uuid5>`-style and
# hadith ids are `hdt:<corpus>:<collection>:<book>:<hadith>`.
_NAR_ZUHRI = "nar:az-zuhri-0001"
_HDT_INTENTIONS = "hdt:lk:bukhari:1:1"


def test_narrator_chains_found(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/graph/narrator/{id}/chains returns one summary per hadith.

    With no reified Chain nodes, the chain is identified by its hadith id, so
    ``chain_id == hadith_id`` (#1032).
    """
    mock_neo4j.execute_read.side_effect = [
        # exists check
        [{"id": _NAR_ZUHRI}],
        # hadiths whose isnad includes the narrator (NARRATED ∪ TRANSMITTED_TO)
        [
            {
                "hadith_id": _HDT_INTENTIONS,
                "matn_ar": "إنما الأعمال بالنيات",
                "matn_en": "Actions are by intentions",
                "grade": "sahih",
            }
        ],
    ]
    resp = client.get(f"/api/v1/graph/narrator/{_NAR_ZUHRI}/chains")
    assert resp.status_code == 200
    body = resp.json()
    assert body["narrator_id"] == _NAR_ZUHRI
    assert body["total"] == 1
    assert body["chains"][0]["hadith_id"] == _HDT_INTENTIONS
    assert body["chains"][0]["chain_id"] == _HDT_INTENTIONS


def test_narrator_chains_reconstructs_from_edges_not_chain_nodes(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """The chains query must NOT target nonexistent Chain nodes (#1032).

    It reconstructs membership from NARRATED + per-hadith TRANSMITTED_TO edges.
    """
    mock_neo4j.execute_read.side_effect = [
        [{"id": _NAR_ZUHRI}],
        [],
    ]
    resp = client.get(f"/api/v1/graph/narrator/{_NAR_ZUHRI}/chains")
    assert resp.status_code == 200
    cypher = mock_neo4j.execute_read.call_args_list[1][0][0]
    assert "TRANSMITTED_TO" in cypher
    assert "NARRATED" in cypher
    # Regression guard: the old stub matched (c:Chain {hadith_id: ...}).
    assert ":Chain" not in cypher


def test_narrator_chains_empty(client: TestClient, mock_neo4j: MagicMock) -> None:
    """A narrator with no isnad membership returns an empty, well-formed list."""
    mock_neo4j.execute_read.side_effect = [
        [{"id": _NAR_ZUHRI}],
        [],
    ]
    resp = client.get(f"/api/v1/graph/narrator/{_NAR_ZUHRI}/chains")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["chains"] == []


def test_narrator_chains_not_found(client: TestClient) -> None:
    """GET /api/v1/graph/narrator/{id}/chains returns 404 for unknown narrator."""
    resp = client.get("/api/v1/graph/narrator/nonexistent/chains")
    assert resp.status_code == 404


def test_hadith_chain_found(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/graph/hadith/{id}/chain rebuilds the ordered chain from edges."""
    mock_neo4j.execute_read.side_effect = [
        # exists check
        [{"id": _HDT_INTENTIONS}],
        # ordered TRANSMITTED_TO edges tagged with this hadith id
        [
            {
                "position": 0,
                "source_id": "nar:umar-0001",
                "source_name_ar": "عمر بن الخطاب",
                "source_name_en": "Umar ibn al-Khattab",
                "source_gen": "companion",
                "target_id": "nar:alqama-0002",
                "target_name_ar": "علقمة بن وقاص",
                "target_name_en": "Alqama ibn Waqqas",
                "target_gen": "successor",
            },
            {
                "position": 1,
                "source_id": "nar:alqama-0002",
                "source_name_ar": "علقمة بن وقاص",
                "source_name_en": "Alqama ibn Waqqas",
                "source_gen": "successor",
                "target_id": _NAR_ZUHRI,
                "target_name_ar": "محمد بن مسلم الزهري",
                "target_name_en": "Ibn Shihab al-Zuhri",
                "target_gen": "tabi_tabiin",
            },
        ],
    ]
    resp = client.get(f"/api/v1/graph/hadith/{_HDT_INTENTIONS}/chain")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hadith_id"] == _HDT_INTENTIONS
    # 3 distinct narrators across 2 consecutive transmission edges
    assert len(body["nodes"]) == 3
    assert len(body["edges"]) == 2
    assert body["edges"][0]["relationship"] == "TRANSMITTED_TO"
    # Edges carry their position so the consumer can render in chain order
    assert [e["position"] for e in body["edges"]] == [0, 1]
    # The chain query keys off the TRANSMITTED_TO edge, not Chain nodes (#1032)
    cypher = mock_neo4j.execute_read.call_args_list[1][0][0]
    assert "TRANSMITTED_TO {hadith_id: $id}" in cypher
    assert ":Chain" not in cypher


def test_hadith_chain_empty_when_no_transmission_edges(
    client: TestClient, mock_neo4j: MagicMock
) -> None:
    """A hadith with no TRANSMITTED_TO edges yields an empty (not errored) chain."""
    mock_neo4j.execute_read.side_effect = [
        [{"id": _HDT_INTENTIONS}],
        [],
    ]
    resp = client.get(f"/api/v1/graph/hadith/{_HDT_INTENTIONS}/chain")
    assert resp.status_code == 200
    body = resp.json()
    assert body["nodes"] == []
    assert body["edges"] == []


def test_hadith_chain_not_found(client: TestClient) -> None:
    """GET /api/v1/graph/hadith/{id}/chain returns 404 for unknown hadith."""
    resp = client.get("/api/v1/graph/hadith/nonexistent/chain")
    assert resp.status_code == 404


def test_narrator_network_found(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/graph/narrator/{id}/network returns ego network."""
    _narrator_fields = {
        "id": "nar-001",
        "name_ar": "الراوي المركزي",
        "name_en": "Central Narrator",
        "gen": "companion",
        "community_id": 1,
        "in_degree": 2,
        "out_degree": 3,
        "betweenness_centrality": 0.05,
        "pagerank": 0.002,
        "sect_affiliation": "sunni",
        "trustworthiness_consensus": "thiqah",
        "death_year_ah": 59,
        "birth_year_ah": None,
        "kunya": None,
        "nisba": None,
    }
    mock_neo4j.execute_read.side_effect = [
        # 1: exists check
        [{"id": "nar-001"}],
        # 2: center node fields
        [_narrator_fields],
        # 3: neighbors at depth
        [
            {
                **_narrator_fields,
                "id": "nar-010",
                "name_ar": "المعلم",
                "name_en": "Teacher",
                "gen": "companion",
            },
            {
                **_narrator_fields,
                "id": "nar-020",
                "name_ar": "الطالب",
                "name_en": "Student",
                "gen": "successor",
            },
        ],
        # 4: TRANSMITTED_TO edges
        [
            {"source": "nar-010", "target": "nar-001", "rel": "TRANSMITTED_TO", "weight": 1},
            {"source": "nar-001", "target": "nar-020", "rel": "TRANSMITTED_TO", "weight": 1},
        ],
        # 5: STUDIED_UNDER edges
        [],
    ]
    resp = client.get("/api/v1/graph/narrator/nar-001/network")
    assert resp.status_code == 200
    body = resp.json()
    assert body["narrator_id"] == "nar-001"
    assert body["teachers"] == 1
    assert body["students"] == 1
    assert len(body["nodes"]) == 3  # center + teacher + student
    assert len(body["edges"]) == 2


def test_narrator_network_not_found(client: TestClient) -> None:
    """GET /api/v1/graph/narrator/{id}/network returns 404 for unknown narrator."""
    resp = client.get("/api/v1/graph/narrator/nonexistent/network")
    assert resp.status_code == 404
