"""Tests for auth middleware and protected endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.auth.tokens import create_access_token, create_refresh_token


class TestProtectedEndpoints:
    """Protected /api/v1/ endpoints should return 401 without a token."""

    def test_narrators_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/narrators")
        assert resp.status_code == 401

    def test_hadiths_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/hadiths")
        assert resp.status_code == 401

    def test_collections_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/collections")
        assert resp.status_code == 401

    def test_narrators_accessible_with_token(
        self, client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        mock_neo4j.execute_read.return_value = []
        token = create_access_token("test-user")
        resp = client.get(
            "/api/v1/narrators",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code != 401


class TestPublicEndpoints:
    """Health and auth endpoints should be accessible without a token."""

    def test_health_is_public(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code != 401

    def test_auth_login_is_public(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/login/google")
        assert resp.status_code != 401

    def test_auth_me_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestAuthMeEndpoint:
    def test_returns_user_info(self, client: TestClient) -> None:
        token = create_access_token("my-user-id")
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "my-user-id"

    def test_rejects_refresh_token(self, client: TestClient) -> None:
        token = create_refresh_token("my-user-id")
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401


class TestRefreshEndpoint:
    CSRF_TOKEN = "test-csrf-token-value"

    def _set_csrf(self, client: TestClient) -> dict[str, str]:
        """Set CSRF cookie and return the header for the request."""
        client.cookies.set("csrf_token", self.CSRF_TOKEN)
        return {"X-CSRF-Token": self.CSRF_TOKEN}

    def test_refresh_returns_new_tokens(self, client: TestClient) -> None:
        refresh = create_refresh_token("my-user-id")
        client.cookies.set("refresh_token", refresh)
        headers = self._set_csrf(client)
        resp = client.post("/api/v1/auth/refresh", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # Refresh token is now in httpOnly cookie, not in response body
        assert data["refresh_token"] == ""

    def test_refresh_sets_httponly_cookie(self, client: TestClient) -> None:
        refresh = create_refresh_token("my-user-id")
        client.cookies.set("refresh_token", refresh)
        headers = self._set_csrf(client)
        resp = client.post("/api/v1/auth/refresh", headers=headers)
        assert resp.status_code == 200
        # The Set-Cookie header should contain the new refresh token
        cookies = resp.headers.get_list("set-cookie")
        refresh_cookie = [c for c in cookies if "refresh_token=" in c]
        assert len(refresh_cookie) > 0
        assert "httponly" in refresh_cookie[0].lower()

    def test_refresh_requires_csrf(self, client: TestClient) -> None:
        refresh = create_refresh_token("my-user-id")
        client.cookies.set("refresh_token", refresh)
        # No CSRF token — should be rejected
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code == 403

    def test_refresh_rejects_csrf_mismatch(self, client: TestClient) -> None:
        refresh = create_refresh_token("my-user-id")
        client.cookies.set("refresh_token", refresh)
        client.cookies.set("csrf_token", "cookie-value")
        resp = client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": "different-value"},
        )
        assert resp.status_code == 403

    def test_refresh_missing_cookie(self, client: TestClient) -> None:
        headers = self._set_csrf(client)
        resp = client.post("/api/v1/auth/refresh", headers=headers)
        assert resp.status_code == 401

    def test_refresh_with_invalid_token(self, client: TestClient) -> None:
        client.cookies.set("refresh_token", "garbage")
        headers = self._set_csrf(client)
        resp = client.post("/api/v1/auth/refresh", headers=headers)
        assert resp.status_code == 401

    def test_refresh_with_access_token_rejected(self, client: TestClient) -> None:
        access = create_access_token("my-user-id")
        client.cookies.set("refresh_token", access)
        headers = self._set_csrf(client)
        resp = client.post("/api/v1/auth/refresh", headers=headers)
        assert resp.status_code == 401
