"""SEC-01: Authentication bypass tests.

Verifies that protected endpoints reject requests with missing, expired,
forged, and wrong-type tokens. Covers OWASP Testing Guide OTG-AUTHN-*.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# Representative protected endpoints (auth-required and admin-required).
PROTECTED_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/v1/narrators"),
    ("GET", "/api/v1/hadiths"),
    ("GET", "/api/v1/collections"),
    ("GET", "/api/v1/search?q=test"),
    ("GET", "/api/v1/narrators/fake-id"),
    ("GET", "/api/v1/hadiths/fake-id"),
]

ADMIN_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/users/some-user-id"),
    ("GET", "/api/v1/admin/health/live"),
    ("GET", "/api/v1/admin/stats"),
]


class TestMissingToken:
    """Requests without any Authorization header must return 401."""

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_protected_endpoint_rejects_no_token(
        self, client: TestClient, method: str, path: str
    ) -> None:
        response = client.request(method, path)
        assert response.status_code == 401, (
            f"{method} {path} should return 401 without token, got {response.status_code}"
        )

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_admin_endpoint_rejects_no_token(
        self, client: TestClient, method: str, path: str
    ) -> None:
        response = client.request(method, path)
        assert response.status_code == 401


class TestExpiredToken:
    """Requests with an expired JWT must return 401."""

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_expired_token_rejected(
        self, client: TestClient, expired_token: str, method: str, path: str
    ) -> None:
        response = client.request(
            method, path, headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_expired_token_rejected_admin(
        self, client: TestClient, expired_token: str, method: str, path: str
    ) -> None:
        response = client.request(
            method, path, headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert response.status_code == 401


class TestForgedToken:
    """Requests with a token signed by the wrong secret must return 401."""

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_forged_token_rejected(
        self, client: TestClient, forged_token: str, method: str, path: str
    ) -> None:
        response = client.request(method, path, headers={"Authorization": f"Bearer {forged_token}"})
        assert response.status_code == 401


class TestWrongTokenType:
    """A refresh token must not be accepted where an access token is required."""

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_refresh_token_rejected_on_protected(
        self,
        client: TestClient,
        refresh_token_as_access: str,
        method: str,
        path: str,
    ) -> None:
        response = client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {refresh_token_as_access}"},
        )
        assert response.status_code == 401


class TestMalformedAuthHeaders:
    """Various malformed Authorization header values must return 401."""

    @pytest.mark.parametrize(
        "header_value",
        [
            "",
            "Basic dXNlcjpwYXNz",
            "Bearer",
            "Bearer ",
            "bearer valid-looking-but-lowercase",
            "Token some-token",
            "not-a-jwt-at-all",
        ],
    )
    def test_malformed_header_rejected(self, client: TestClient, header_value: str) -> None:
        response = client.get("/api/v1/narrators", headers={"Authorization": header_value})
        assert response.status_code == 401


class TestTokenWithMissingSub:
    """A token without the 'sub' claim must be rejected."""

    def test_missing_sub_claim(self, client: TestClient) -> None:
        import secrets as stdlib_secrets
        from datetime import UTC, datetime, timedelta

        from jose import jwt

        from tests.test_security.conftest import _TEST_ALGORITHM, _TEST_SECRET

        payload = {
            "type": "access",
            "exp": datetime.now(UTC) + timedelta(minutes=30),
            "iat": datetime.now(UTC),
            "jti": stdlib_secrets.token_hex(16),
            # No "sub" claim
        }
        token = jwt.encode(payload, _TEST_SECRET, algorithm=_TEST_ALGORITHM)
        response = client.get(
            "/api/v1/narrators",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401
