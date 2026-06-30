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
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from src.api.auth import User
from src.api.routes.admin.data import PurgeRequest, data_overview, data_sources, purge_source

_ADMIN_TOKEN = "admin-jwt-token"


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
    """The data sub-router is mounted under the admin group with its routes."""
    from src.api.routes.admin import router as admin_router

    paths = {route.path for route in admin_router.routes}  # type: ignore[attr-defined]
    assert "/data/overview" in paths
    assert "/data/sources" in paths
    assert "/data/purge" in paths


def _admin() -> User:
    return User(id="admin-1", email="admin@example.com", name="Admin One", role="admin")


def _purge_read(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Stand-in for execute_read against a graph holding one purgeable corpus."""
    q = " ".join(query.split())
    corpus = (params or {}).get("corpus")
    if corpus != "thaqalayn":
        # An unknown corpus matches nothing — preview counts are all zero.
        return []
    if "UNWIND labels(n) AS label" in q:
        return [
            {"label": "Hadith", "c": 7},
            {"label": "Collection", "c": 1},
        ]
    if "count(DISTINCT r)" in q:
        return [
            {"rel_type": "APPEARS_IN", "c": 7},
            {"rel_type": "NARRATED", "c": 12},
        ]
    return []


def _purge_client() -> MagicMock:
    client = MagicMock()
    client.execute_read.side_effect = _purge_read
    client.execute_write.return_value = []
    return client


class TestPurgeSource:
    def test_dry_run_previews_without_writing(self) -> None:
        client = _purge_client()
        resp = purge_source(
            body=PurgeRequest(source_corpus="thaqalayn", dry_run=True),
            admin=_admin(),
            neo4j=client,
            token=_ADMIN_TOKEN,
        )

        assert resp.dry_run is True
        assert resp.deleted is False
        assert resp.total_nodes == 8
        assert resp.total_relationships == 19
        by_label = {n.label: n.count for n in resp.node_counts}
        assert by_label == {"Hadith": 7, "Collection": 1}
        # Counts are sorted by descending count.
        assert [n.label for n in resp.node_counts] == ["Hadith", "Collection"]
        # A dry run NEVER writes to the graph.
        client.execute_write.assert_not_called()

    def test_real_run_requires_matching_confirmation(self) -> None:
        client = _purge_client()
        with pytest.raises(HTTPException) as exc:
            purge_source(
                body=PurgeRequest(source_corpus="thaqalayn", dry_run=False, confirmation="wrong"),
                admin=_admin(),
                neo4j=client,
                token=_ADMIN_TOKEN,
            )
        assert exc.value.status_code == 400
        # Aborted before any destructive write.
        client.execute_write.assert_not_called()

    def test_real_run_missing_confirmation_aborts(self) -> None:
        client = _purge_client()
        with pytest.raises(HTTPException) as exc:
            purge_source(
                body=PurgeRequest(source_corpus="thaqalayn", dry_run=False),
                admin=_admin(),
                neo4j=client,
                token=_ADMIN_TOKEN,
            )
        assert exc.value.status_code == 400
        client.execute_write.assert_not_called()

    def test_real_run_deletes_and_audits(self) -> None:
        client = _purge_client()
        with patch("src.api.routes.admin.data.create_audit_entry") as mock_audit:
            resp = purge_source(
                body=PurgeRequest(
                    source_corpus="thaqalayn", dry_run=False, confirmation="thaqalayn"
                ),
                admin=_admin(),
                neo4j=client,
                token=_ADMIN_TOKEN,
            )

        assert resp.dry_run is False
        assert resp.deleted is True
        assert resp.total_nodes == 8
        assert resp.total_relationships == 19

        # The only graph write is the corpus-scoped DETACH DELETE — the audit
        # trail is no longer an AUDIT_LOG node write (ig#1140).
        writes = [c.args[0] for c in client.execute_write.call_args_list]
        assert len(writes) == 1
        assert "DETACH DELETE" in writes[0]
        assert client.execute_write.call_args_list[0].args[1] == {"corpus": "thaqalayn"}
        assert not any("AUDIT_LOG" in w for w in writes)

        # The audit entry is recorded against user-service, forwarding the
        # admin's bearer token and the actor identity.
        mock_audit.assert_called_once()
        call = mock_audit.call_args
        assert call.args[0] == _ADMIN_TOKEN
        assert call.kwargs["action"] == "data.purge_source"
        assert call.kwargs["actor_id"] == "admin-1"
        assert call.kwargs["actor_name"] == "Admin One"
        assert "thaqalayn" in call.kwargs["details"]

    def test_audit_failure_does_not_fail_completed_purge(self) -> None:
        """If user-service is unreachable, the already-completed purge succeeds."""
        client = _purge_client()
        with patch(
            "src.api.routes.admin.data.create_audit_entry",
            side_effect=httpx.ConnectError("user-service down"),
        ):
            resp = purge_source(
                body=PurgeRequest(
                    source_corpus="thaqalayn", dry_run=False, confirmation="thaqalayn"
                ),
                admin=_admin(),
                neo4j=client,
                token=_ADMIN_TOKEN,
            )

        # Best-effort: the destructive write already landed, so the response is
        # still a successful deletion despite the audit POST failing.
        assert resp.deleted is True
        assert resp.total_nodes == 8

    def test_blank_corpus_is_rejected(self) -> None:
        client = _purge_client()
        with pytest.raises(HTTPException) as exc:
            purge_source(
                body=PurgeRequest(source_corpus="   ", dry_run=True),
                admin=_admin(),
                neo4j=client,
                token=_ADMIN_TOKEN,
            )
        assert exc.value.status_code == 422
        client.execute_write.assert_not_called()

    def test_write_failure_surfaces_503(self) -> None:
        client = _purge_client()
        client.execute_write.side_effect = RuntimeError("neo4j down")
        with pytest.raises(HTTPException) as exc:
            purge_source(
                body=PurgeRequest(
                    source_corpus="thaqalayn", dry_run=False, confirmation="thaqalayn"
                ),
                admin=_admin(),
                neo4j=client,
                token=_ADMIN_TOKEN,
            )
        assert exc.value.status_code == 503
