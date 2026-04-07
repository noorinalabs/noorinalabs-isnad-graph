"""Tests for admin reports endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware import require_admin
from src.auth.models import User
from tests.test_api.test_admin import _admin_user, _test_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    test_settings = _test_settings()
    from src.config import get_settings

    get_settings.cache_clear()

    import src.config

    monkeypatch.setattr(src.config, "get_settings", lambda: test_settings)


@pytest.fixture
def mock_neo4j() -> MagicMock:
    client = MagicMock()
    client.execute_read.return_value = []
    client.execute_write.return_value = []
    return client


@pytest.fixture
def admin_app(mock_neo4j: MagicMock) -> FastAPI:
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    app.dependency_overrides[require_admin] = _admin_user
    return app


@pytest.fixture
def admin_client(admin_app: FastAPI) -> TestClient:
    return TestClient(admin_app)


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
    @pytest.fixture
    def noauth_app(self, mock_neo4j: MagicMock) -> FastAPI:
        from src.api.app import create_app

        app = create_app()
        app.state.neo4j = mock_neo4j
        return app

    @pytest.fixture
    def noauth_client(self, noauth_app: FastAPI) -> TestClient:
        return TestClient(noauth_app)

    @pytest.fixture
    def regular_app(self, mock_neo4j: MagicMock) -> FastAPI:
        from fastapi import HTTPException

        from src.api.app import create_app

        app = create_app()
        app.state.neo4j = mock_neo4j

        def _raise_forbidden() -> User:
            raise HTTPException(status_code=403, detail="Admin access required")

        app.dependency_overrides[require_admin] = _raise_forbidden
        return app

    @pytest.fixture
    def regular_client(self, regular_app: FastAPI) -> TestClient:
        return TestClient(regular_app)

    def test_reports_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.get("/api/v1/admin/reports")
        assert resp.status_code == 401

    def test_reports_403(self, regular_client: TestClient) -> None:
        resp = regular_client.get("/api/v1/admin/reports")
        assert resp.status_code == 403
