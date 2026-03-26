"""Tests for JWT token creation and verification."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
        assert "jti" in payload

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

    def test_revoked_access_token_rejected(self) -> None:
        token = create_access_token("user-revoke-access")
        verify_token(token)
        revoke_token(token)
        with pytest.raises(ValueError, match="revoked"):
            verify_token(token)

    def test_revoke_garbage_does_not_raise(self) -> None:
        revoke_token("not-a-jwt")


class TestRedisBackedRevocation:
    """Test Redis-backed token blacklist (#235)."""

    def test_revoke_uses_redis_when_available(self) -> None:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.exists.return_value = 0

        token = create_refresh_token("user-redis")

        with patch("src.auth.tokens.get_redis_client", return_value=mock_redis):
            revoke_token(token)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0].startswith("revoked_token:")
        assert call_args[0][2] == "1"

    def test_verify_checks_redis_when_available(self) -> None:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.exists.return_value = 1  # Token is revoked in Redis

        token = create_refresh_token("user-redis-check")

        with patch("src.auth.tokens.get_redis_client", return_value=mock_redis):
            with pytest.raises(ValueError, match="revoked"):
                verify_token(token)

    def test_falls_back_to_memory_when_redis_unavailable(self) -> None:
        with patch("src.auth.tokens.get_redis_client", return_value=None):
            token = create_refresh_token("user-fallback")
            revoke_token(token)
            with pytest.raises(ValueError, match="revoked"):
                verify_token(token)

    def test_revoke_ttl_matches_token_expiry(self) -> None:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        token = create_refresh_token("user-ttl", expires_days=1)

        with patch("src.auth.tokens.get_redis_client", return_value=mock_redis):
            revoke_token(token)

        call_args = mock_redis.setex.call_args
        ttl = call_args[0][1]
        # TTL should be roughly 1 day (86400s), allow some tolerance
        assert 86300 < ttl <= 86400
