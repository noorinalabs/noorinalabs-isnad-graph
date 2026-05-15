"""Tests for admin auth enforcement across all admin endpoints.

The ``noauth_client`` / ``regular_client`` fixtures and the
``_clear_settings_cache`` autouse shim live in ``tests/test_api/conftest.py``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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
