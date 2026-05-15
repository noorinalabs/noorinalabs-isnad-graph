"""Factory helpers for Neo4j-result-shaped test dictionaries.

The API tests mock ``Neo4jClient.execute_read`` and assert on the JSON the
route builds from those rows. Each route reads a specific *shape* of row, so
these factories are grouped by the shape the consuming route expects — not by
domain entity. A single ``make_narrator_*`` is deliberately split into three
because the ``/narrators`` list row, the ``/graph/.../network`` node row, and
the ``/search`` hit row are genuinely different dictionaries (different keys,
e.g. ``generation`` vs ``gen``); collapsing them would force tests to assert
against a shape their route never actually produces.

Every factory takes ``**overrides`` so a test can pin the one or two fields it
cares about while the rest stay at sensible defaults. Each call returns a
fresh dict, so tests can mutate the result without bleeding into siblings.

These complement — they do not replace — the ``sample_narrator`` /
``sample_hadith`` fixtures in ``conftest.py``, which return frozen Pydantic
*model* instances for the model-layer tests. The API tests need raw dicts.
"""

from __future__ import annotations

from typing import Any


def make_narrator_row(**overrides: Any) -> dict[str, Any]:
    """A NARRATOR node's ``props`` as read by the ``/narrators`` list/detail routes.

    Wrap in ``{"props": make_narrator_row()}`` to match the Cypher output the
    route iterates.
    """
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
    """A HADITH node's ``props`` as read by the ``/hadiths`` list/detail routes.

    Wrap in ``{"props": make_hadith_row()}`` to match the Cypher output.
    """
    return {
        "id": "hdt:lk:abu_dawud:10:1574",
        "matn_ar": "إنما الأعمال بالنيات",
        "matn_en": "Actions are by intentions",
        "source_corpus": "lk",
        "collection_name": "abu_dawud",
        **overrides,
    }


def make_collection_row(**overrides: Any) -> dict[str, Any]:
    """A COLLECTION node's ``props`` as read by the ``/collections`` routes.

    Wrap in ``{"props": make_collection_row()}`` to match the Cypher output.
    """
    return {
        "id": "col-001",
        "name_ar": "صحيح البخاري",
        "name_en": "Sahih al-Bukhari",
        "sect": "sunni",
        **overrides,
    }


def make_chain_row(**overrides: Any) -> dict[str, Any]:
    """A chain row as read by ``/graph/narrator/{id}/chains``.

    Unlike the node factories above this is *not* ``props``-wrapped — the
    chains query projects these fields directly.
    """
    return {
        "chain_id": "ch-001",
        "hadith_id": "had-001",
        "matn_ar": "متن الحديث",
        "matn_en": "Hadith text",
        "grade": "sahih",
        **overrides,
    }


def make_narrator_node(**overrides: Any) -> dict[str, Any]:
    """A narrator row as read by ``/graph/narrator/{id}/network``.

    Distinct from :func:`make_narrator_row`: the network query projects
    ``gen`` (not ``generation``) and adds the centrality/degree metrics the
    ego-graph response needs. Not ``props``-wrapped.
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


def make_search_narrator_hit(**overrides: Any) -> dict[str, Any]:
    """A narrator full-text search hit as read by the ``/search`` route."""
    return {
        "id": "nar-001",
        "name_ar": "اختبار",
        "name_en": "test narrator",
        "score": 2.5,
        **overrides,
    }


def make_search_hadith_hit(**overrides: Any) -> dict[str, Any]:
    """A hadith full-text search hit as read by the ``/search`` route."""
    return {
        "id": "had-001",
        "matn_ar": "نص اختبار",
        "matn_en": "test hadith text",
        "score": 1.8,
        **overrides,
    }
