"""Tests for graph traversal endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


def test_narrator_chains_found(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/graph/narrator/{id}/chains returns chains."""
    mock_neo4j.execute_read.side_effect = [
        # exists check
        [{"id": "nar-001"}],
        # chain rows
        [
            {
                "chain_id": "ch-001",
                "hadith_id": "had-001",
                "matn_ar": "متن الحديث",
                "matn_en": "Hadith text",
                "grade": "sahih",
            }
        ],
    ]
    resp = client.get("/api/v1/graph/narrator/nar-001/chains")
    assert resp.status_code == 200
    body = resp.json()
    assert body["narrator_id"] == "nar-001"
    assert body["total"] == 1
    assert body["chains"][0]["chain_id"] == "ch-001"


def test_narrator_chains_with_max_depth(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/graph/narrator/{id}/chains respects max_depth parameter."""
    mock_neo4j.execute_read.side_effect = [
        # exists check
        [{"id": "nar-001"}],
        # chain rows
        [
            {
                "chain_id": "ch-001",
                "hadith_id": "had-001",
                "matn_ar": "متن الحديث",
                "matn_en": "Hadith text",
                "grade": "sahih",
            }
        ],
    ]
    resp = client.get("/api/v1/graph/narrator/nar-001/chains?max_depth=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    # Verify the Cypher query used the custom depth
    cypher = mock_neo4j.execute_read.call_args_list[1][0][0]
    assert "TRANSMITTED_TO*1..3" in cypher


def test_narrator_chains_default_max_depth(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/graph/narrator/{id}/chains uses default max_depth=5."""
    mock_neo4j.execute_read.side_effect = [
        [{"id": "nar-001"}],
        [
            {
                "chain_id": "ch-001",
                "hadith_id": "had-001",
                "matn_ar": "متن",
                "matn_en": None,
                "grade": None,
            }
        ],
    ]
    resp = client.get("/api/v1/graph/narrator/nar-001/chains")
    assert resp.status_code == 200
    cypher = mock_neo4j.execute_read.call_args_list[1][0][0]
    assert "TRANSMITTED_TO*1..5" in cypher


def test_narrator_chains_max_depth_validation(client: TestClient) -> None:
    """GET /api/v1/graph/narrator/{id}/chains rejects invalid max_depth."""
    resp = client.get("/api/v1/graph/narrator/nar-001/chains?max_depth=0")
    assert resp.status_code == 422

    resp = client.get("/api/v1/graph/narrator/nar-001/chains?max_depth=11")
    assert resp.status_code == 422


def test_narrator_chains_not_found(client: TestClient) -> None:
    """GET /api/v1/graph/narrator/{id}/chains returns 404 for unknown narrator."""
    resp = client.get("/api/v1/graph/narrator/nonexistent/chains")
    assert resp.status_code == 404


def test_hadith_chain_found(client: TestClient, mock_neo4j: MagicMock) -> None:
    """GET /api/v1/graph/hadith/{id}/chain returns chain visualization."""
    mock_neo4j.execute_read.side_effect = [
        # exists check
        [{"id": "had-001"}],
        # chain visualization rows
        [
            {
                "chain_id": "ch-001",
                "source_id": "nar-001",
                "source_name_ar": "الراوي الأول",
                "source_name_en": "Narrator One",
                "source_gen": "companion",
                "target_id": "nar-002",
                "target_name_ar": "الراوي الثاني",
                "target_name_en": "Narrator Two",
                "target_gen": "successor",
            }
        ],
    ]
    resp = client.get("/api/v1/graph/hadith/had-001/chain")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hadith_id"] == "had-001"
    assert len(body["nodes"]) == 2
    assert len(body["edges"]) == 1
    assert body["edges"][0]["relationship"] == "TRANSMITTED_TO"


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
