"""Tests for admin API endpoints.

Shared fixtures (``mock_neo4j``, ``admin_app``/``admin_client``,
``noauth_app``/``noauth_client``, ``regular_app``/``regular_client``, the
``_clear_settings_cache`` autouse shim) and the ``_admin_user`` /
``_regular_user`` / ``_test_settings`` helpers live in
``tests/test_api/conftest.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# --- Health endpoints ---


class TestAdminHealth:
    def test_liveness(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_readiness(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        """Readiness reports ok when every service is reachable via its accessor.

        Postgres is mocked at the ``PgClient`` wrapper and Redis at the
        ``get_redis_client`` helper — both imported into the admin health
        module — so the probe exercises the same accessors the application
        uses for real traffic. ``PgClient`` is used as a context manager.
        """
        mock_neo4j.execute_read.return_value = [{"ok": 1}]

        mock_pg = MagicMock()
        mock_pg.execute.return_value = [{"?column?": 1}]
        mock_pg_cls = MagicMock()
        mock_pg_cls.return_value.__enter__.return_value = mock_pg
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with (
            patch("src.api.routes.admin.health.PgClient", mock_pg_cls),
            patch(
                "src.api.routes.admin.health.get_redis_client",
                return_value=mock_redis,
            ),
        ):
            resp = admin_client.get("/api/v1/admin/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["neo4j"] is True
        assert data["postgres"] is True
        assert data["redis"] is True

    def test_readiness_degraded_when_pg_down(
        self, admin_client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        """Readiness reports degraded (not 500) when a service accessor fails."""
        mock_neo4j.execute_read.return_value = [{"ok": 1}]

        mock_pg = MagicMock()
        mock_pg.execute.side_effect = RuntimeError("connection refused")
        mock_pg_cls = MagicMock()
        mock_pg_cls.return_value.__enter__.return_value = mock_pg
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with (
            patch("src.api.routes.admin.health.PgClient", mock_pg_cls),
            patch(
                "src.api.routes.admin.health.get_redis_client",
                return_value=mock_redis,
            ),
        ):
            resp = admin_client.get("/api/v1/admin/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["postgres"] is False
        assert data["neo4j"] is True
        assert data["redis"] is True


# --- Stats endpoint ---


class TestAdminStats:
    def test_stats_empty(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hadith_count"] == 0
        assert data["narrator_count"] == 0
        assert data["collection_count"] == 0
        assert data["coverage_pct"] == 0.0

    def test_stats_with_data(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.return_value = [
            {
                "hadith_count": 100,
                "narrator_count": 50,
                "collection_count": 6,
                "coverage_pct": 85.5,
            }
        ]
        resp = admin_client.get("/api/v1/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hadith_count"] == 100
        assert data["narrator_count"] == 50


# --- Analytics endpoint ---


class TestAdminAnalytics:
    def test_analytics(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert "search_volume" in data
        assert "api_call_count" in data
        assert "popular_narrators" in data


# --- Users endpoints ---


class TestAdminUsers:
    """User management endpoints now return 501 (moved to user-service)."""

    def test_list_users_returns_501(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/users")
        assert resp.status_code == 501

    def test_get_user_returns_501(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/users/u1")
        assert resp.status_code == 501

    def test_update_user_returns_501(self, admin_client: TestClient) -> None:
        resp = admin_client.patch("/api/v1/admin/users/u1", json={"is_admin": True})
        assert resp.status_code == 501

    def test_update_user_role_returns_501(self, admin_client: TestClient) -> None:
        resp = admin_client.patch("/api/v1/admin/users/u1/role", json={"role": "admin"})
        assert resp.status_code == 501


# --- Config endpoints ---


class TestAdminConfig:
    @pytest.fixture(autouse=True)
    def _setup_pg(self, admin_app: FastAPI) -> None:
        """Override the get_pg dependency with a mock PgClient."""
        from src.api.deps import get_pg

        self._pg = MagicMock()
        # Default: no rows in system_config, no rows in config_audit
        self._pg.execute.return_value = []
        admin_app.dependency_overrides[get_pg] = lambda: self._pg

    def test_get_config_defaults(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_limit_per_minute"] == 60
        assert data["cors_origins"] == ["http://localhost:3000"]
        assert data["feature_flags"] == {}
        assert data["max_search_results"] == 100
        assert data["max_pagination_limit"] == 100

    def test_get_config_from_db(self, admin_client: TestClient) -> None:
        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "SELECT key, value FROM system_config" in query:
                return [
                    {"key": "rate_limit_per_minute", "value": "120"},
                    {"key": "cors_origins", "value": '["http://example.com"]'},
                ]
            return []

        self._pg.execute.side_effect = fake_execute
        resp = admin_client.get("/api/v1/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_limit_per_minute"] == 120
        assert data["cors_origins"] == ["http://example.com"]
        # Defaults for missing keys
        assert data["max_search_results"] == 100

    def test_update_config(self, admin_client: TestClient) -> None:
        self._pg.execute.return_value = []
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"rate_limit_per_minute": 120},
        )
        assert resp.status_code == 200
        # Verify upsert and audit INSERT calls were made
        calls = self._pg.execute.call_args_list
        upsert_calls = [c for c in calls if "INSERT INTO system_config" in str(c)]
        audit_calls = [c for c in calls if "INSERT INTO config_audit" in str(c)]
        assert len(upsert_calls) >= 1
        assert len(audit_calls) >= 1

    def test_update_config_no_fields(self, admin_client: TestClient) -> None:
        resp = admin_client.patch("/api/v1/admin/config", json={})
        assert resp.status_code == 400

    def test_update_config_rejects_unknown_fields(self, admin_client: TestClient) -> None:
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"jwt_secret": "hacked"},
        )
        # Unknown field is ignored by pydantic, so no valid fields → 400
        assert resp.status_code == 400

    def test_audit_log_empty(self, admin_client: TestClient) -> None:
        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "count(*)" in query:
                return [{"total": 0}]
            return []

        self._pg.execute.side_effect = fake_execute
        resp = admin_client.get("/api/v1/admin/config/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries"] == []
        assert data["total"] == 0

    def test_audit_log_with_entries(self, admin_client: TestClient) -> None:
        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "count(*)" in query:
                return [{"total": 1}]
            if "SELECT key, old_value" in query:
                return [
                    {
                        "key": "rate_limit_per_minute",
                        "old_value": "60",
                        "new_value": "120",
                        "changed_by": "admin-user",
                        "changed_at": "2026-03-16 12:00:00+00",
                    }
                ]
            return []

        self._pg.execute.side_effect = fake_execute
        resp = admin_client.get("/api/v1/admin/config/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["entries"]) == 1
        assert data["entries"][0]["key"] == "rate_limit_per_minute"
        assert data["entries"][0]["old_value"] == "60"
        assert data["entries"][0]["new_value"] == "120"
