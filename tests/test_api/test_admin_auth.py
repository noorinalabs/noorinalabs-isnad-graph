"""Tests for admin auth enforcement across all admin endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.auth import User
from src.api.middleware import require_admin
from tests.test_api.test_admin import _test_settings


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
    """App with non-admin user — all admin endpoints should return 404 (ig#804)."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j

    def _raise_not_found() -> User:
        # Mirrors require_admin's hide-existence 404 for non-admins (ig#804).
        raise HTTPException(status_code=404, detail="Not Found")

    app.dependency_overrides[require_admin] = _raise_not_found
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

    def test_post_data_purge_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.post(
            "/api/v1/admin/data/purge",
            json={"source_corpus": "thaqalayn", "dry_run": True},
        )
        assert resp.status_code == 401


class TestAllEndpoints404:
    """Verify every admin endpoint returns 404 (not 403) for non-admin users.

    A 404 hides the existence of the admin surface from authenticated non-admins
    who could otherwise distinguish a forbidden-but-real route from a missing one
    (ig#804). See ``test_require_admin_guard`` below for the unit-level proof.
    """

    @pytest.mark.parametrize("endpoint", ADMIN_GET_ENDPOINTS)
    def test_get_endpoints_404(self, regular_client: TestClient, endpoint: str) -> None:
        resp = regular_client.get(endpoint)
        assert resp.status_code == 404, f"{endpoint} returned {resp.status_code}"

    def test_patch_moderation_404(self, regular_client: TestClient) -> None:
        resp = regular_client.patch("/api/v1/admin/moderation/some-id", json={"status": "approved"})
        assert resp.status_code == 404

    def test_post_flag_404(self, regular_client: TestClient) -> None:
        resp = regular_client.post(
            "/api/v1/admin/moderation/flag",
            json={"entity_type": "hadith", "entity_id": "h1", "reason": "test"},
        )
        assert resp.status_code == 404

    def test_patch_config_404(self, regular_client: TestClient) -> None:
        resp = regular_client.patch("/api/v1/admin/config", json={"rate_limit_per_minute": 10})
        assert resp.status_code == 404

    def test_patch_user_404(self, regular_client: TestClient) -> None:
        resp = regular_client.patch("/api/v1/admin/users/u1", json={"is_admin": True})
        assert resp.status_code == 404

    def test_post_data_purge_404(self, regular_client: TestClient) -> None:
        resp = regular_client.post(
            "/api/v1/admin/data/purge",
            json={"source_corpus": "thaqalayn", "dry_run": True},
        )
        assert resp.status_code == 404


class TestRequireAdminGuard:
    """Unit-level proof of the ``require_admin`` guard contract (ig#804).

    Exercises the guard function directly — admin / non-admin / anonymous /
    auth-backend-down — by stubbing ``require_auth``, so the status-code mapping
    is pinned independently of router wiring. The request object is never read by
    the guard once ``require_auth`` is stubbed, so a bare ``MagicMock`` suffices.
    """

    @staticmethod
    def _user(role: str) -> User:
        return User(id="u1", email="u@example.com", name="u", role=role)

    @pytest.mark.asyncio
    async def test_admin_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.api.middleware as mw

        async def _auth(_request: object) -> User:
            return self._user("admin")

        monkeypatch.setattr(mw, "require_auth", _auth)
        user = await mw.require_admin(MagicMock())
        assert user.role == "admin"

    @pytest.mark.asyncio
    async def test_non_admin_raises_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.api.middleware as mw

        async def _auth(_request: object) -> User:
            return self._user("viewer")

        monkeypatch.setattr(mw, "require_auth", _auth)
        with pytest.raises(HTTPException) as exc:
            await mw.require_admin(MagicMock())
        # 404 (not 403) + the default detail so it is indistinguishable from a
        # genuinely missing route.
        assert exc.value.status_code == 404
        assert exc.value.detail == "Not Found"

    @pytest.mark.asyncio
    async def test_anonymous_propagates_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.api.middleware as mw

        async def _auth(_request: object) -> User:
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        monkeypatch.setattr(mw, "require_auth", _auth)
        with pytest.raises(HTTPException) as exc:
            await mw.require_admin(MagicMock())
        # Anonymous stays 401 — uniform across every authed route, so it does not
        # single out the admin surface the way a 403-vs-404 differential would.
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_backend_down_propagates_503(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import src.api.middleware as mw

        async def _auth(_request: object) -> User:
            raise HTTPException(status_code=503, detail="Authentication service unavailable")

        monkeypatch.setattr(mw, "require_auth", _auth)
        with pytest.raises(HTTPException) as exc:
            await mw.require_admin(MagicMock())
        assert exc.value.status_code == 503
