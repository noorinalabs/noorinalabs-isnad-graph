"""Factory functions for Neo4j-result-shaped dicts used in API tests.

The fixtures in ``tests/conftest.py`` return Pydantic model instances. API
tests instead need raw ``dict``s shaped like the rows returned by Cypher
queries (the values that ``mock_neo4j.execute_read.return_value`` /
``side_effect`` produce). These factories own those default shapes so that
schema changes don't have to be propagated test-by-test.

Each factory takes ``**overrides`` and returns a fresh dict per call.
"""

from __future__ import annotations

from typing import Any


def make_narrator_row(**overrides: Any) -> dict[str, Any]:
    """Narrator props dict — the shape returned by ``MATCH (n:Narrator) RETURN n {.*}``."""
    return {
        "id": "nar-001",
        "name_ar": "أبو هريرة",
        "name_en": "Abu Hurayra",
        "generation": "companion",
        "gender": "male",
        "sect_affiliation": "sunni",
        "trustworthiness_consensus": "thiqah",
        **overrides,
    }


def make_hadith_row(**overrides: Any) -> dict[str, Any]:
    """Hadith props dict — shape returned by ``MATCH (h:Hadith) RETURN h {.*}``."""
    return {
        "id": "hdt:lk:abu_dawud:10:1574",
        "matn_ar": "إنما الأعمال بالنيات",
        "matn_en": "Actions are by intentions",
        "source_corpus": "lk",
        "collection_name": "abu_dawud",
        **overrides,
    }


def make_collection_row(**overrides: Any) -> dict[str, Any]:
    """Collection props dict — shape returned by ``MATCH (c:Collection) RETURN c {.*}``."""
    return {
        "id": "col-001",
        "name_ar": "صحيح البخاري",
        "name_en": "Sahih al-Bukhari",
        "sect": "sunni",
        **overrides,
    }


def make_chain_row(**overrides: Any) -> dict[str, Any]:
    """Chain row — shape returned by the narrator-chains traversal query."""
    return {
        "chain_id": "ch-001",
        "hadith_id": "had-001",
        "matn_ar": "متن الحديث",
        "matn_en": "Hadith text",
        "grade": "sahih",
        **overrides,
    }


def make_network_narrator_row(**overrides: Any) -> dict[str, Any]:
    """Narrator row with Phase-4 enrichment metrics, as returned by the ego-network query.

    Includes betweenness_centrality, in_degree, out_degree, pagerank, community_id —
    nullable enrichment fields defined in ``ontology/domain.yaml``.
    """
    return {
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
        **overrides,
    }


def make_chain_edge_row(**overrides: Any) -> dict[str, Any]:
    """Edge row from the hadith-chain visualization query (TRANSMITTED_TO segment)."""
    return {
        "chain_id": "ch-001",
        "source_id": "nar-001",
        "source_name_ar": "الراوي الأول",
        "source_name_en": "Narrator One",
        "source_gen": "companion",
        "target_id": "nar-002",
        "target_name_ar": "الراوي الثاني",
        "target_name_en": "Narrator Two",
        "target_gen": "successor",
        **overrides,
    }


def make_narrator_search_hit(**overrides: Any) -> dict[str, Any]:
    """Search-result row for narrator fulltext queries (id + names + score)."""
    return {
        "id": "nar-001",
        "name_ar": "اختبار",
        "name_en": "test narrator",
        "score": 2.5,
        **overrides,
    }


def make_hadith_search_hit(**overrides: Any) -> dict[str, Any]:
    """Search-result row for hadith fulltext/semantic queries (id + matn + score)."""
    return {
        "id": "had-001",
        "matn_ar": "نص اختبار",
        "matn_en": "test hadith text",
        "score": 1.8,
        **overrides,
    }
