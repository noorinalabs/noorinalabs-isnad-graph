"""Tests for user-service JWKS-based RS256 JWT validation."""

from __future__ import annotations

import secrets
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwt


def _generate_rsa_keypair() -> tuple[rsa.RSAPrivateKey, bytes, dict[str, object]]:
    """Generate an RSA private key and return (private_key, pem, jwks_dict)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )

    # Build JWKS from the public key
    pub = private_key.public_key()
    pub_numbers = pub.public_numbers()

    import base64

    def _int_to_b64(n: int, length: int) -> str:
        return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()

    jwks = {
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


def _make_token(
    claims: dict[str, object] | None = None,
    *,
    expired: bool = False,
    key: bytes | None = None,
    algorithm: str = "RS256",
) -> str:
    """Create a signed JWT with the given claims."""
    now = int(time.time())
    payload: dict[str, object] = {
        "sub": "user-123",
        "email": "test@example.com",
        "roles": ["researcher"],
        "subscription_status": "active",
        "type": "access",
        "exp": now - 100 if expired else now + 3600,
        "iat": now - 200 if expired else now,
        "jti": secrets.token_hex(16),
    }
    if claims:
        payload.update(claims)
    return str(jwt.encode(payload, key or _PEM, algorithm=algorithm))


class TestJWKSFetch:
    """Test JWKS fetching and caching."""

    def test_fetch_jwks_caches_result(self) -> None:
        from src.api.auth import fetch_jwks, invalidate_jwks_cache

        invalidate_jwks_cache()
        with patch("src.api.auth.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = _JWKS
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            result1 = fetch_jwks()
            result2 = fetch_jwks()

            assert result1 == _JWKS
            assert result2 == _JWKS
            # Should only call once due to caching
            mock_get.assert_called_once()

        invalidate_jwks_cache()

    def test_fetch_jwks_raises_on_unreachable(self) -> None:
        from src.api.auth import fetch_jwks, invalidate_jwks_cache

        invalidate_jwks_cache()
        with patch("src.api.auth.httpx.get", side_effect=httpx.ConnectError("unreachable")):
            with pytest.raises(httpx.ConnectError):
                fetch_jwks()
        invalidate_jwks_cache()


class TestVerifyUserServiceToken:
    """Test RS256 JWT verification against JWKS."""

    def test_valid_token(self) -> None:
        from src.api.auth import invalidate_jwks_cache, verify_user_service_token

        invalidate_jwks_cache()
        token = _make_token()
        with patch("src.api.auth.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = _JWKS
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            payload = verify_user_service_token(token)

        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert payload["roles"] == ["researcher"]
        invalidate_jwks_cache()

    def test_expired_token_raises(self) -> None:
        from src.api.auth import invalidate_jwks_cache, verify_user_service_token

        invalidate_jwks_cache()
        token = _make_token(expired=True)
        with patch("src.api.auth.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = _JWKS
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            with pytest.raises(ValueError, match="Invalid token"):
                verify_user_service_token(token)
        invalidate_jwks_cache()

    def test_invalid_signature_raises(self) -> None:
        from src.api.auth import invalidate_jwks_cache, verify_user_service_token

        invalidate_jwks_cache()
        # Sign with a different key
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pem = other_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        token = _make_token(key=other_pem)
        with patch("src.api.auth.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = _JWKS
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            with pytest.raises(ValueError, match="Invalid token"):
                verify_user_service_token(token)
        invalidate_jwks_cache()

    def test_jwks_unreachable_raises_http_error(self) -> None:
        from src.api.auth import invalidate_jwks_cache, verify_user_service_token

        invalidate_jwks_cache()
        token = _make_token()
        with patch("src.api.auth.httpx.get", side_effect=httpx.ConnectError("down")):
            with pytest.raises(httpx.ConnectError):
                verify_user_service_token(token)
        invalidate_jwks_cache()


class TestRequireAuth:
    """Test require_auth dependency with user-service JWTs."""

    def test_missing_header_returns_401(self, client: TestClient) -> None:
        resp = client.get("/api/v1/narrators")
        assert resp.status_code == 401

    def test_malformed_header_returns_401(self, client: TestClient) -> None:
        resp = client.get(
            "/api/v1/narrators",
            headers={"Authorization": "Basic abc123"},
        )
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        with patch("src.api.auth.verify_user_service_token", side_effect=ValueError("bad")):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": "Bearer invalid-token"},
            )
        assert resp.status_code == 401

    def test_jwks_unavailable_returns_503(self, client: TestClient) -> None:
        with patch(
            "src.api.auth.verify_user_service_token",
            side_effect=httpx.ConnectError("unreachable"),
        ):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": "Bearer some-token"},
            )
        assert resp.status_code == 503

    def test_valid_token_grants_access(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.return_value = []
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "roles": ["researcher"],
            "subscription_status": "active",
            "type": "access",
        }
        with patch("src.api.auth.verify_user_service_token", return_value=payload):
            resp = client.get(
                "/api/v1/narrators",
                headers={"Authorization": "Bearer valid-token"},
            )
        assert resp.status_code != 401
        assert resp.status_code != 503


class TestRoleBasedAccess:
    """Test role mapping from JWT roles claim."""

    def test_admin_role_mapped(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        payload = {
            "sub": "admin-user",
            "email": "admin@example.com",
            "roles": ["admin"],
            "subscription_status": "active",
            "type": "access",
        }
        mock_neo4j.execute_read.return_value = []
        with patch("src.api.auth.verify_user_service_token", return_value=payload):
            # Admin endpoints should be accessible
            resp = client.get(
                "/api/v1/admin/users",
                headers={"Authorization": "Bearer admin-token"},
            )
        # Should not get 403
        assert resp.status_code != 403

    def test_viewer_cannot_access_admin(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        payload = {
            "sub": "viewer-user",
            "email": "viewer@example.com",
            "roles": ["reader"],
            "subscription_status": "active",
            "type": "access",
        }
        with patch("src.api.auth.verify_user_service_token", return_value=payload):
            resp = client.get(
                "/api/v1/admin/users",
                headers={"Authorization": "Bearer viewer-token"},
            )
        # Non-admins get 404, not 403 — the admin surface is hidden (ig#804).
        assert resp.status_code == 404

    def test_researcher_maps_to_editor(self) -> None:
        from src.api.auth import Role
        from src.api.middleware import _resolve_role

        assert _resolve_role(["researcher"]) == Role.EDITOR

    def test_highest_role_wins(self) -> None:
        from src.api.auth import Role
        from src.api.middleware import _resolve_role

        assert _resolve_role(["reader", "admin"]) == Role.ADMIN

    def test_empty_roles_default_to_viewer(self) -> None:
        from src.api.auth import Role
        from src.api.middleware import _resolve_role

        assert _resolve_role([]) == Role.VIEWER
