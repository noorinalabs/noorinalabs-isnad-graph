"""Tests for admin auth enforcement across all admin endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.middleware import require_admin
from src.auth.models import User
from tests.test_api.test_admin import _test_settings


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
def noauth_app(mock_neo4j: MagicMock) -> FastAPI:
    """App with no auth overrides — all admin endpoints should return 401."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    return app


@pytest.fixture
def noauth_client(noauth_app: FastAPI) -> TestClient:
    return TestClient(noauth_app)


@pytest.fixture
def regular_app(mock_neo4j: MagicMock) -> FastAPI:
    """App with non-admin user — all admin endpoints should return 403."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j

    def _raise_forbidden() -> User:
        raise HTTPException(status_code=403, detail="Admin access required")

    app.dependency_overrides[require_admin] = _raise_forbidden
    return app


@pytest.fixture
def regular_client(regular_app: FastAPI) -> TestClient:
    return TestClient(regular_app)


# All admin GET endpoints that should be protected
ADMIN_GET_ENDPOINTS = [
    "/api/v1/admin/health/live",
    "/api/v1/admin/health/ready",
    "/api/v1/admin/stats",
    "/api/v1/admin/analytics",
    "/api/v1/admin/users",
    "/api/v1/admin/moderation",
    "/api/v1/admin/reports",
    "/api/v1/admin/config",
    "/api/v1/admin/config/audit",
]


class TestAllEndpoints401:
    """Verify every admin endpoint returns 401 without auth."""

    @pytest.mark.parametrize("endpoint", ADMIN_GET_ENDPOINTS)
    def test_get_endpoints_401(self, noauth_client: TestClient, endpoint: str) -> None:
        resp = noauth_client.get(endpoint)
        assert resp.status_code == 401, f"{endpoint} returned {resp.status_code}"

    def test_patch_moderation_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.patch("/api/v1/admin/moderation/some-id", json={"status": "approved"})
        assert resp.status_code == 401

    def test_post_flag_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.post(
            "/api/v1/admin/moderation/flag",
            json={"entity_type": "hadith", "entity_id": "h1", "reason": "test"},
        )
        assert resp.status_code == 401

    def test_patch_config_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.patch("/api/v1/admin/config", json={"rate_limit_per_minute": 10})
        assert resp.status_code == 401

    def test_patch_user_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.patch("/api/v1/admin/users/u1", json={"is_admin": True})
        assert resp.status_code == 401


class TestAllEndpoints403:
    """Verify every admin endpoint returns 403 for non-admin users."""

    @pytest.mark.parametrize("endpoint", ADMIN_GET_ENDPOINTS)
    def test_get_endpoints_403(self, regular_client: TestClient, endpoint: str) -> None:
        resp = regular_client.get(endpoint)
        assert resp.status_code == 403, f"{endpoint} returned {resp.status_code}"

    def test_patch_moderation_403(self, regular_client: TestClient) -> None:
        resp = regular_client.patch("/api/v1/admin/moderation/some-id", json={"status": "approved"})
        assert resp.status_code == 403

    def test_post_flag_403(self, regular_client: TestClient) -> None:
        resp = regular_client.post(
            "/api/v1/admin/moderation/flag",
            json={"entity_type": "hadith", "entity_id": "h1", "reason": "test"},
        )
        assert resp.status_code == 403

    def test_patch_config_403(self, regular_client: TestClient) -> None:
        resp = regular_client.patch("/api/v1/admin/config", json={"rate_limit_per_minute": 10})
        assert resp.status_code == 403

    def test_patch_user_403(self, regular_client: TestClient) -> None:
        resp = regular_client.patch("/api/v1/admin/users/u1", json={"is_admin": True})
        assert resp.status_code == 403
