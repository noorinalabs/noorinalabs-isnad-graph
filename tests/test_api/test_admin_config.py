"""Tests for admin config endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import User
from src.api.middleware import require_admin
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
        assert data["log_retention_days"] == 7

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


class TestLogRetention:
    """ig#1038 — configurable 'keep last X days' log retention knob."""

    def test_round_trip(self, admin_client: TestClient, mock_pg: MagicMock) -> None:
        # Persist a new value, then read it back from the (mocked) DB.
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"log_retention_days": 30},
        )
        assert resp.status_code == 200
        calls = mock_pg.execute.call_args_list
        upserts = [c for c in calls if "INSERT INTO system_config" in str(c)]
        # The serialized value lands in the upsert params.
        assert any("log_retention_days" in str(c) and "30" in str(c) for c in upserts)

        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "SELECT key, value FROM system_config" in query:
                return [{"key": "log_retention_days", "value": "30"}]
            return []

        mock_pg.execute.side_effect = fake_execute
        read_back = admin_client.get("/api/v1/admin/config")
        assert read_back.status_code == 200
        assert read_back.json()["log_retention_days"] == 30

    def test_rejects_below_min(self, admin_client: TestClient) -> None:
        resp = admin_client.patch("/api/v1/admin/config", json={"log_retention_days": 0})
        assert resp.status_code == 422

    def test_rejects_above_max(self, admin_client: TestClient) -> None:
        resp = admin_client.patch("/api/v1/admin/config", json={"log_retention_days": 366})
        assert resp.status_code == 422

    def test_non_admin_cannot_set(self, mock_neo4j: MagicMock) -> None:
        from fastapi import HTTPException

        from src.api.app import create_app

        app = create_app()
        app.state.neo4j = mock_neo4j

        def _raise_not_found() -> User:
            raise HTTPException(status_code=404, detail="Not Found")

        app.dependency_overrides[require_admin] = _raise_not_found
        client = TestClient(app)
        resp = client.patch("/api/v1/admin/config", json={"log_retention_days": 14})
        assert resp.status_code == 404

    def test_propagates_to_loki_on_change(
        self, admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Updating the knob drives the Loki runtime overrides write (enforcement).
        import src.api.routes.admin.config as config_route

        calls: list[int] = []
        monkeypatch.setattr(config_route, "apply_loki_retention", lambda days: calls.append(days))

        resp = admin_client.patch("/api/v1/admin/config", json={"log_retention_days": 45})
        assert resp.status_code == 200
        assert calls == [45]

    def test_no_loki_write_for_unrelated_change(
        self, admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A config update that doesn't touch retention must not write the Loki file.
        import src.api.routes.admin.config as config_route

        calls: list[int] = []
        monkeypatch.setattr(config_route, "apply_loki_retention", lambda days: calls.append(days))

        resp = admin_client.patch("/api/v1/admin/config", json={"rate_limit_per_minute": 120})
        assert resp.status_code == 200
        assert calls == []


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

        def _raise_not_found() -> User:
            # Mirrors require_admin's hide-existence 404 for non-admins (ig#804).
            raise HTTPException(status_code=404, detail="Not Found")

        app.dependency_overrides[require_admin] = _raise_not_found
        return app

    @pytest.fixture
    def regular_client(self, regular_app: FastAPI) -> TestClient:
        return TestClient(regular_app)

    def test_get_config_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.get("/api/v1/admin/config")
        assert resp.status_code == 401

    def test_get_config_404(self, regular_client: TestClient) -> None:
        resp = regular_client.get("/api/v1/admin/config")
        assert resp.status_code == 404

    def test_patch_config_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.patch("/api/v1/admin/config", json={"rate_limit_per_minute": 10})
        assert resp.status_code == 401

    def test_patch_config_404(self, regular_client: TestClient) -> None:
        resp = regular_client.patch("/api/v1/admin/config", json={"rate_limit_per_minute": 10})
        assert resp.status_code == 404

    def test_audit_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.get("/api/v1/admin/config/audit")
        assert resp.status_code == 401

    def test_audit_404(self, regular_client: TestClient) -> None:
        resp = regular_client.get("/api/v1/admin/config/audit")
        assert resp.status_code == 404
