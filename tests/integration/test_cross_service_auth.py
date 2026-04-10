"""Cross-service auth integration tests.

Verifies the full authentication flow between user-service (JWT issuer)
and isnad-graph (JWT consumer) using real RSA key generation and the
actual JWKS validation pipeline.

Scenarios covered:
1. Valid JWT from user-service grants access to isnad-graph API
2. Expired JWT rejected with 401
3. Refreshed JWT (new jti, fresh exp) accepted
4. Role-based access control across services
5. User-service JWKS endpoint down returns 503
6. Token with wrong type claim rejected with 401
"""

from __future__ import annotations

import base64
import os
import secrets
import time
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from src.config import (
    AuthSettings,
    Neo4jSettings,
    PostgresSettings,
    RedisSettings,
    Settings,
    get_settings,
)

# ---------------------------------------------------------------------------
# RSA key material (generated once per module)
# ---------------------------------------------------------------------------


def _int_to_b64(n: int, length: int) -> str:
    return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()


def _generate_rsa_keypair() -> tuple[rsa.RSAPrivateKey, bytes, dict[str, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_numbers = private_key.public_key().public_numbers()
    jwks: dict[str, object] = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "test-key-1",
                "n": _int_to_b64(pub_numbers.n, 256),
                "e": _int_to_b64(pub_numbers.e, 3),
            }
        ]
    }
    return private_key, pem, jwks


_PRIVATE_KEY, _PEM, _JWKS = _generate_rsa_keypair()

# A second keypair to simulate key rotation / wrong-key scenarios
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_PEM = _OTHER_KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    for key in list(os.environ):
        if key.startswith(("NEO4J_", "PG_", "REDIS_", "AUTH_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("PG_DSN", raising=False)
    return Settings(
        _env_file=None,
        neo4j=Neo4jSettings(
            _env_file=None, uri="bolt://localhost:7687", user="neo4j", password="test"
        ),
        postgres=PostgresSettings(_env_file=None, dsn="postgresql://test:test@localhost:5432/test"),
        redis=RedisSettings(_env_file=None, url="redis://localhost:6379/0"),
        auth=AuthSettings(
            _env_file=None,
            user_service_url="http://localhost:8001",
            user_service_jwks_cache_ttl=3600,
        ),
    )


@pytest.fixture(autouse=True)
def _patch_settings(test_settings: Settings) -> Iterator[None]:
    targets = [
        "src.config.get_settings",
        "src.auth.jwks.get_settings",
    ]
    patches = [patch(t, return_value=test_settings) for t in targets]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture(autouse=True)
def _invalidate_jwks_cache() -> Iterator[None]:
    """Ensure JWKS cache is clean before and after each test."""
    from src.auth.jwks import invalidate_jwks_cache

    invalidate_jwks_cache()
    yield
    invalidate_jwks_cache()


@pytest.fixture
def mock_neo4j() -> MagicMock:
    client = MagicMock()
    client.execute_read.return_value = []
    client.execute_write.return_value = []
    return client


@pytest.fixture
def app(mock_neo4j: MagicMock) -> FastAPI:
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _mock_jwks_response() -> MagicMock:
    """Return a mock httpx response that serves _JWKS."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = _JWKS
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _make_token(
    *,
    sub: str = "user-123",
    email: str = "test@example.com",
    roles: list[str] | None = None,
    token_type: str = "access",
    expired: bool = False,
    key: bytes | None = None,
    extra_claims: dict[str, object] | None = None,
) -> str:
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": sub,
        "email": email,
        "roles": roles or ["researcher"],
        "subscription_status": "active",
        "type": token_type,
        "exp": now - 100 if expired else now + 3600,
        "iat": now - 200 if expired else now,
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)
    return str(jwt.encode(payload, key or _PEM, algorithm="RS256"))


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------


class TestValidTokenFlow:
    """Scenario 1: User authenticates via user-service, receives JWT,
    accesses isnad-graph API successfully."""

    def test_valid_jwt_grants_api_access(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        token = _make_token()
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200

    def test_valid_jwt_populates_user_context(
        self, client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        """The middleware should extract user info from the JWT claims."""
        token = _make_token(sub="user-456", email="scholar@example.com", roles=["admin"])
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"},
            )
        # Admin endpoint accessible — user context was correctly resolved
        assert resp.status_code != 401
        assert resp.status_code != 403


class TestExpiredTokenRejection:
    """Scenario 2: Expired JWT is rejected by isnad-graph with 401."""

    def test_expired_jwt_returns_401(self, client: TestClient) -> None:
        token = _make_token(expired=True)
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 401


class TestRefreshedToken:
    """Scenario 3: A refreshed JWT (new jti, fresh expiry) is accepted."""

    def test_refreshed_token_accepted(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        # First token (simulates the original)
        token_1 = _make_token()
        # Second token (simulates a refreshed token — new jti, fresh exp)
        token_2 = _make_token()

        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp_1 = client.get(
                "/api/v1/narrators",
                headers={"Authorization": f"Bearer {token_1}"},
            )
            resp_2 = client.get(
                "/api/v1/narrators",
                headers={"Authorization": f"Bearer {token_2}"},
            )
        assert resp_1.status_code == 200
        assert resp_2.status_code == 200


class TestRoleBasedAccessControl:
    """Scenario 4: Role-based access control works across services."""

    def test_admin_role_accesses_admin_endpoints(
        self, client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        token = _make_token(roles=["admin"])
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code != 403

    def test_viewer_blocked_from_admin_endpoints(self, client: TestClient) -> None:
        token = _make_token(roles=["reader"])
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 403

    def test_moderator_blocked_from_admin_endpoints(self, client: TestClient) -> None:
        token = _make_token(roles=["moderator"])
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 403

    def test_researcher_maps_to_editor_role(
        self, client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        token = _make_token(roles=["researcher"])
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200

    def test_multiple_roles_uses_highest_privilege(
        self, client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        token = _make_token(roles=["reader", "admin"])
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code != 403


class TestUserServiceDown:
    """Scenario 5: User-service JWKS endpoint unreachable returns 503."""

    def test_jwks_unreachable_returns_503(self, client: TestClient) -> None:
        token = _make_token()
        with patch("src.auth.jwks.httpx.get", side_effect=httpx.ConnectError("connection refused")):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 503

    def test_jwks_timeout_returns_503(self, client: TestClient) -> None:
        token = _make_token()
        with patch("src.auth.jwks.httpx.get", side_effect=httpx.ReadTimeout("timeout")):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 503


class TestTokenRevocation:
    """Scenario 6: Tokens signed with a revoked/rotated key are rejected."""

    def test_token_signed_with_wrong_key_returns_401(self, client: TestClient) -> None:
        """Simulates token revocation via key rotation — a token signed with
        the old key fails verification against the new JWKS."""
        token = _make_token(key=_OTHER_PEM)
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 401

    def test_non_access_token_type_rejected(self, client: TestClient) -> None:
        """A refresh token should not be accepted as an access token."""
        token = _make_token(token_type="refresh")
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 401

    def test_missing_authorization_header_returns_401(self, client: TestClient) -> None:
        resp = client.get("/api/v1/narrators")
        assert resp.status_code == 401

    def test_malformed_bearer_token_returns_401(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/narrators",
            headers={"Authorization": "Bearer not-a-jwt"},
        )
        # Will fail JWKS verification or JWT decode
        with patch("src.auth.jwks.httpx.get", return_value=_mock_jwks_response()):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": "Bearer not-a-jwt"},
            )
        assert resp.status_code == 401
