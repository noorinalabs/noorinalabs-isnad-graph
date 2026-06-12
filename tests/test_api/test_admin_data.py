"""Tests for admin data-management endpoints.

These exercise the route handlers directly with a mocked Neo4jClient rather
than through ``TestClient``.  Building multiple ``create_app()`` instances
OOM-kills the in-sandbox runner; direct calls keep the unit logic fully
covered without that cost.  Admin auth-gating is enforced at the router-group
level (``dependencies=[Depends(require_admin)]`` in ``create_app``) and is
covered by ``test_admin_auth`` for every sub-router, including this one — see
``test_data_router_is_registered`` for the wiring check.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.api.routes.admin.data import data_overview, data_sources


def _loaded_read(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Stand-in for Neo4jClient.execute_read against a small loaded graph."""
    q = " ".join(query.split())
    if "CALL db.labels()" in q:
        return [{"label": "Hadith"}, {"label": "Narrator"}, {"label": "Collection"}]
    if "CALL db.relationshipTypes()" in q:
        return [{"relationshipType": "NARRATED"}, {"relationshipType": "APPEARS_IN"}]
    if "source_corpus" in q:
        if "(n:`Hadith`)" in q:
            return [{"source": "sunnah", "c": 40}, {"source": "thaqalayn", "c": 7}]
        if "(n:`Collection`)" in q:
            return [{"source": "sunnah", "c": 2}, {"source": "thaqalayn", "c": 1}]
        return []
    if "(n:`Hadith`)" in q:
        return [{"c": 47}]
    if "(n:`Narrator`)" in q:
        return [{"c": 120}]
    if "(n:`Collection`)" in q:
        return [{"c": 3}]
    if "[r:`NARRATED`]" in q:
        return [{"c": 200}]
    if "[r:`APPEARS_IN`]" in q:
        return [{"c": 47}]
    return []


def _loaded_client() -> MagicMock:
    client = MagicMock()
    client.execute_read.side_effect = _loaded_read
    return client


def _empty_client() -> MagicMock:
    client = MagicMock()
    client.execute_read.return_value = []
    return client


def _broken_client() -> MagicMock:
    client = MagicMock()
    client.execute_read.side_effect = RuntimeError("neo4j down")
    return client


class TestDataOverview:
    def test_inventory(self) -> None:
        resp = data_overview(neo4j=_loaded_client())

        # Only labels with a non-zero count appear, sorted by count desc.
        assert [n.label for n in resp.node_counts] == ["Narrator", "Hadith", "Collection"]
        assert resp.total_nodes == 47 + 120 + 3
        assert [r.rel_type for r in resp.relationship_counts] == ["NARRATED", "APPEARS_IN"]
        assert resp.total_relationships == 200 + 47

    def test_empty_graph(self) -> None:
        resp = data_overview(neo4j=_empty_client())
        assert resp.node_counts == []
        assert resp.relationship_counts == []
        assert resp.total_nodes == 0
        assert resp.total_relationships == 0

    def test_neo4j_unavailable_degrades(self) -> None:
        resp = data_overview(neo4j=_broken_client())
        assert resp.total_nodes == 0
        assert resp.total_relationships == 0


class TestDataSources:
    def test_provenance_breakdown(self) -> None:
        resp = data_sources(neo4j=_loaded_client())

        assert resp.distinct_sources == 2
        assert resp.total_hadiths == 47
        assert resp.total_collections == 3
        by_source = {s.source_corpus: s for s in resp.sources}
        assert by_source["sunnah"].hadith_count == 40
        assert by_source["sunnah"].collection_count == 2
        assert by_source["thaqalayn"].hadith_count == 7
        assert by_source["thaqalayn"].collection_count == 1

    def test_empty(self) -> None:
        resp = data_sources(neo4j=_empty_client())
        assert resp.sources == []
        assert resp.distinct_sources == 0
        assert resp.total_hadiths == 0
        assert resp.total_collections == 0

    def test_unavailable_degrades(self) -> None:
        resp = data_sources(neo4j=_broken_client())
        assert resp.sources == []
        assert resp.distinct_sources == 0


def test_data_router_is_registered() -> None:
    """The data sub-router is mounted under the admin group with both routes."""
    from src.api.routes.admin import router as admin_router

    paths = {route.path for route in admin_router.routes}  # type: ignore[attr-defined]
    assert "/data/overview" in paths
    assert "/data/sources" in paths
