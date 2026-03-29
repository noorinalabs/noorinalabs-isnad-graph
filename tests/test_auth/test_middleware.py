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
    def test_refresh_returns_new_tokens(self, client: TestClient) -> None:
        refresh = create_refresh_token("my-user-id")
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        # Tokens must be in httpOnly cookies, not in the response body
        assert "access_token" not in data
        assert "refresh_token" not in data
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

    def test_refresh_with_invalid_token(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "garbage"},
        )
        assert resp.status_code == 401

    def test_refresh_with_access_token_rejected(self, client: TestClient) -> None:
        access = create_access_token("my-user-id")
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access},
        )
        assert resp.status_code == 401
