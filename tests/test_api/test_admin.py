"""Tests for admin API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware import require_admin
from src.auth.models import User
from src.config import (
    AuthSettings,
    Neo4jSettings,
    PostgresSettings,
    RedisSettings,
    Settings,
    get_settings,
)


def _admin_user() -> User:
    return User(
        id="admin-user",
        email="admin@example.com",
        name="Admin User",
        provider="jwt",
        provider_user_id="admin-user",
        created_at=datetime.now(UTC),
        is_admin=True,
    )


def _regular_user() -> User:
    return User(
        id="regular-user",
        email="user@example.com",
        name="Regular User",
        provider="jwt",
        provider_user_id="regular-user",
        created_at=datetime.now(UTC),
        is_admin=False,
    )


def _test_settings() -> Settings:
    """Build a Settings instance without reading .env."""
    return Settings(
        _env_file=None,
        neo4j=Neo4jSettings(uri="bolt://localhost:7687", user="neo4j", password="test"),
        postgres=PostgresSettings(dsn="postgresql://test:test@localhost:5432/test"),
        redis=RedisSettings(url="redis://localhost:6379/0"),
        auth=AuthSettings(),
    )


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch get_settings to avoid .env parsing errors in tests."""
    test_settings = _test_settings()
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
    """FastAPI app with admin auth override."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    app.dependency_overrides[require_admin] = _admin_user
    return app


@pytest.fixture
def admin_client(admin_app: FastAPI) -> TestClient:
    return TestClient(admin_app)


@pytest.fixture
def noauth_app(mock_neo4j: MagicMock) -> FastAPI:
    """FastAPI app with NO auth overrides — tests 401/403 paths."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    return app


@pytest.fixture
def noauth_client(noauth_app: FastAPI) -> TestClient:
    return TestClient(noauth_app)


@pytest.fixture
def regular_app(mock_neo4j: MagicMock) -> FastAPI:
    """FastAPI app with non-admin user override for require_admin."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j

    from fastapi import HTTPException

    def _raise_forbidden() -> User:
        raise HTTPException(status_code=403, detail="Admin access required")

    app.dependency_overrides[require_admin] = _raise_forbidden
    return app


@pytest.fixture
def regular_client(regular_app: FastAPI) -> TestClient:
    return TestClient(regular_app)


# --- Health endpoints ---


class TestAdminHealth:
    def test_liveness(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_readiness(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.return_value = [{"ok": 1}]
        resp = admin_client.get("/api/v1/admin/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "neo4j" in data
        assert "postgres" in data
        assert "redis" in data


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
    def test_list_users_empty(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_users_with_results(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.side_effect = [
            [{"total": 1}],
            [
                {
                    "u": {
                        "id": "u1",
                        "email": "a@b.com",
                        "name": "Test",
                        "provider": "google",
                        "is_admin": False,
                        "is_suspended": False,
                        "created_at": "2025-01-01T00:00:00",
                        "role": "user",
                    }
                }
            ],
        ]
        resp = admin_client.get("/api/v1/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["email"] == "a@b.com"

    def test_get_user_not_found(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.return_value = []
        resp = admin_client.get("/api/v1/admin/users/nonexistent")
        assert resp.status_code == 404

    def test_get_user(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.return_value = [
            {
                "u": {
                    "id": "u1",
                    "email": "a@b.com",
                    "name": "Test",
                    "provider": "google",
                    "is_admin": False,
                    "is_suspended": False,
                    "created_at": "2025-01-01T00:00:00",
                    "role": None,
                }
            }
        ]
        resp = admin_client.get("/api/v1/admin/users/u1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "u1"

    def test_update_user(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_write.return_value = [
            {
                "u": {
                    "id": "u1",
                    "email": "a@b.com",
                    "name": "Test",
                    "provider": "google",
                    "is_admin": True,
                    "is_suspended": False,
                    "created_at": "2025-01-01T00:00:00",
                    "role": "admin",
                }
            }
        ]
        resp = admin_client.patch(
            "/api/v1/admin/users/u1", json={"is_admin": True, "role": "admin"}
        )
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True

    def test_update_user_no_fields(self, admin_client: TestClient) -> None:
        resp = admin_client.patch("/api/v1/admin/users/u1", json={})
        assert resp.status_code == 400

    def test_update_user_not_found(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_write.return_value = []
        resp = admin_client.patch("/api/v1/admin/users/nonexistent", json={"is_admin": True})
        assert resp.status_code == 404


# --- Auth enforcement ---


class TestAdminAuthEnforcement:
    def test_unauthenticated_returns_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.get("/api/v1/admin/stats")
        assert resp.status_code == 401

    def test_non_admin_returns_403(self, regular_client: TestClient) -> None:
        resp = regular_client.get("/api/v1/admin/stats")
        assert resp.status_code == 403
