"""Tests for admin reports endpoint.

Shared fixtures (``mock_neo4j``, ``admin_client``, ``noauth_client``,
``regular_client``, the ``_clear_settings_cache`` autouse shim) live in
``tests/test_api/conftest.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient


class TestSystemReports:
    def test_reports_returns_structure(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline" in data
        assert "disambiguation" in data
        assert "dedup" in data
        assert "graph_validation" in data
        assert "topic_coverage" in data

    def test_ingestion_sections_always_null(self, admin_client: TestClient) -> None:
        """Pipeline, disambiguation, and dedup are always null after ingestion extraction."""
        resp = admin_client.get("/api/v1/admin/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pipeline"] is None
        assert data["disambiguation"] is None
        assert data["dedup"] is None

    def test_reports_graph_validation(
        self, admin_client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        # Graph validation queries Neo4j — return some data
        mock_neo4j.execute_read.return_value = [
            {
                "orphan_narrators": 5,
                "orphan_hadiths": 2,
                "chain_integrity_pct": 95.5,
                "collection_coverage_pct": 88.0,
            }
        ]
        resp = admin_client.get("/api/v1/admin/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["graph_validation"] is not None
        assert data["graph_validation"]["orphan_narrators"] == 5
        assert data["graph_validation"]["chain_integrity_pct"] == 95.5

    def test_reports_topic_coverage(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        # Topic coverage also queries Neo4j — return after graph validation call
        mock_neo4j.execute_read.side_effect = [
            # graph_validation query
            [
                {
                    "orphan_narrators": 0,
                    "orphan_hadiths": 0,
                    "chain_integrity_pct": 100.0,
                    "collection_coverage_pct": 100.0,
                }
            ],
            # topic_coverage query
            [
                {
                    "total_hadiths": 1000,
                    "classified_count": 800,
                    "coverage_pct": 80.0,
                }
            ],
        ]
        resp = admin_client.get("/api/v1/admin/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic_coverage"] is not None
        assert data["topic_coverage"]["total_hadiths"] == 1000
        assert data["topic_coverage"]["coverage_pct"] == 80.0


class TestReportsAuthEnforcement:
    def test_reports_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.get("/api/v1/admin/reports")
        assert resp.status_code == 401

    def test_reports_403(self, regular_client: TestClient) -> None:
        resp = regular_client.get("/api/v1/admin/reports")
        assert resp.status_code == 403
