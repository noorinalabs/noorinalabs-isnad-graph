"""Tests for admin config endpoints."""

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
    monkeypatch.setenv("ENVIRONMENT", "test")
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
def mock_pg() -> MagicMock:
    pg = MagicMock()
    pg.execute.return_value = []
    return pg


@pytest.fixture
def admin_app(mock_neo4j: MagicMock, mock_pg: MagicMock) -> FastAPI:
    from src.api.app import create_app
    from src.api.deps import get_pg

    app = create_app()
    app.state.neo4j = mock_neo4j
    app.dependency_overrides[require_admin] = _admin_user
    app.dependency_overrides[get_pg] = lambda: mock_pg
    return app


@pytest.fixture
def admin_client(admin_app: FastAPI) -> TestClient:
    return TestClient(admin_app)


class TestGetConfig:
    def test_defaults(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_limit_per_minute"] == 60
        assert data["cors_origins"] == ["http://localhost:3000"]
        assert data["feature_flags"] == {}
        assert data["max_search_results"] == 100
        assert data["max_pagination_limit"] == 100

    def test_from_db(self, admin_client: TestClient, mock_pg: MagicMock) -> None:
        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "SELECT key, value FROM system_config" in query:
                return [
                    {"key": "rate_limit_per_minute", "value": "120"},
                    {"key": "max_search_results", "value": "50"},
                ]
            return []

        mock_pg.execute.side_effect = fake_execute
        resp = admin_client.get("/api/v1/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_limit_per_minute"] == 120
        assert data["max_search_results"] == 50
        # Defaults for missing keys
        assert data["max_pagination_limit"] == 100


class TestUpdateConfig:
    def test_update_allowed_value(self, admin_client: TestClient, mock_pg: MagicMock) -> None:
        mock_pg.execute.return_value = []
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"rate_limit_per_minute": 120},
        )
        assert resp.status_code == 200
        # Verify upsert + audit calls
        calls = mock_pg.execute.call_args_list
        upsert_calls = [c for c in calls if "INSERT INTO system_config" in str(c)]
        audit_calls = [c for c in calls if "INSERT INTO config_audit" in str(c)]
        assert len(upsert_calls) >= 1
        assert len(audit_calls) >= 1

    def test_update_multiple_fields(self, admin_client: TestClient, mock_pg: MagicMock) -> None:
        mock_pg.execute.return_value = []
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"rate_limit_per_minute": 30, "max_search_results": 200},
        )
        assert resp.status_code == 200

    def test_reject_empty_body(self, admin_client: TestClient) -> None:
        resp = admin_client.patch("/api/v1/admin/config", json={})
        assert resp.status_code == 400

    def test_reject_forbidden_key_jwt_secret(self, admin_client: TestClient) -> None:
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"jwt_secret": "hacked"},
        )
        # Unknown field is ignored by pydantic → no valid fields → 400
        assert resp.status_code == 400

    def test_reject_forbidden_key_neo4j_password(self, admin_client: TestClient) -> None:
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"neo4j_password": "hacked"},
        )
        assert resp.status_code == 400

    def test_reject_forbidden_key_pg_dsn(self, admin_client: TestClient) -> None:
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"pg_dsn": "postgresql://hack:hack@evil/db"},
        )
        assert resp.status_code == 400

    def test_invalid_type_rejected(self, admin_client: TestClient) -> None:
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"rate_limit_per_minute": "not_a_number"},
        )
        assert resp.status_code == 422


class TestConfigAudit:
    def test_empty_audit(self, admin_client: TestClient, mock_pg: MagicMock) -> None:
        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "count(*)" in query:
                return [{"total": 0}]
            return []

        mock_pg.execute.side_effect = fake_execute
        resp = admin_client.get("/api/v1/admin/config/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries"] == []
        assert data["total"] == 0

    def test_audit_with_entries(self, admin_client: TestClient, mock_pg: MagicMock) -> None:
        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "count(*)" in query:
                return [{"total": 2}]
            if "SELECT key, old_value" in query:
                return [
                    {
                        "key": "rate_limit_per_minute",
                        "old_value": "60",
                        "new_value": "120",
                        "changed_by": "admin-user",
                        "changed_at": "2026-03-16 12:00:00+00",
                    },
                    {
                        "key": "max_search_results",
                        "old_value": "100",
                        "new_value": "50",
                        "changed_by": "admin-user",
                        "changed_at": "2026-03-16 13:00:00+00",
                    },
                ]
            return []

        mock_pg.execute.side_effect = fake_execute
        resp = admin_client.get("/api/v1/admin/config/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["entries"]) == 2
        assert data["entries"][0]["key"] == "rate_limit_per_minute"
        assert data["entries"][1]["key"] == "max_search_results"

    def test_audit_pagination(self, admin_client: TestClient, mock_pg: MagicMock) -> None:
        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "count(*)" in query:
                return [{"total": 100}]
            return []

        mock_pg.execute.side_effect = fake_execute
        resp = admin_client.get("/api/v1/admin/config/audit?page=2&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 100


class TestConfigAuthEnforcement:
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

    def test_get_config_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.get("/api/v1/admin/config")
        assert resp.status_code == 401

    def test_get_config_403(self, regular_client: TestClient) -> None:
        resp = regular_client.get("/api/v1/admin/config")
        assert resp.status_code == 403

    def test_patch_config_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.patch("/api/v1/admin/config", json={"rate_limit_per_minute": 10})
        assert resp.status_code == 401

    def test_patch_config_403(self, regular_client: TestClient) -> None:
        resp = regular_client.patch("/api/v1/admin/config", json={"rate_limit_per_minute": 10})
        assert resp.status_code == 403

    def test_audit_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.get("/api/v1/admin/config/audit")
        assert resp.status_code == 401

    def test_audit_403(self, regular_client: TestClient) -> None:
        resp = regular_client.get("/api/v1/admin/config/audit")
        assert resp.status_code == 403
