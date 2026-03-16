"""Tests for JWT token creation and verification."""

from __future__ import annotations

import pytest

from src.auth.tokens import (
    _revoked_tokens,
    create_access_token,
    create_refresh_token,
    revoke_token,
    verify_token,
)


@pytest.fixture(autouse=True)
def _clear_revoked() -> None:
    """Clear revoked tokens between tests."""
    _revoked_tokens.clear()


class TestCreateAccessToken:
    def test_creates_valid_token(self) -> None:
        token = create_access_token("user-123")
        payload = verify_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_custom_expiry(self) -> None:
        token = create_access_token("user-123", expires_minutes=1)
        payload = verify_token(token)
        assert payload["sub"] == "user-123"


class TestCreateRefreshToken:
    def test_creates_valid_token(self) -> None:
        token = create_refresh_token("user-456")
        payload = verify_token(token)
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"
        assert "jti" in payload

    def test_custom_expiry(self) -> None:
        token = create_refresh_token("user-456", expires_days=1)
        payload = verify_token(token)
        assert payload["sub"] == "user-456"


class TestVerifyToken:
    def test_rejects_garbage(self) -> None:
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token("not-a-jwt")

    def test_rejects_tampered_token(self) -> None:
        token = create_access_token("user-789")
        parts = token.split(".")
        parts[1] = parts[1] + "tampered"
        tampered = ".".join(parts)
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token(tampered)


class TestRevokeToken:
    def test_revoked_refresh_token_rejected(self) -> None:
        token = create_refresh_token("user-revoke")
        verify_token(token)
        revoke_token(token)
        with pytest.raises(ValueError, match="revoked"):
            verify_token(token)

    def test_revoke_garbage_does_not_raise(self) -> None:
        revoke_token("not-a-jwt")
