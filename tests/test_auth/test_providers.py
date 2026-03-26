"""Tests for OAuth provider abstraction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.auth.providers import (
    PROVIDERS,
    AppleProvider,
    FacebookProvider,
    GitHubProvider,
    GoogleProvider,
    _pkce_store,
    get_provider,
    retrieve_pkce_verifier,
    store_pkce_verifier,
)


@pytest.fixture(autouse=True)
def _clear_pkce_store() -> None:
    """Clear in-memory PKCE store between tests."""
    _pkce_store.clear()


class TestProviderRegistry:
    def test_all_four_providers_registered(self) -> None:
        assert set(PROVIDERS.keys()) == {"google", "apple", "facebook", "github"}

    def test_get_provider_google(self) -> None:
        provider = get_provider("google")
        assert isinstance(provider, GoogleProvider)

    def test_get_provider_apple(self) -> None:
        provider = get_provider("apple")
        assert isinstance(provider, AppleProvider)

    def test_get_provider_facebook(self) -> None:
        provider = get_provider("facebook")
        assert isinstance(provider, FacebookProvider)

    def test_get_provider_github(self) -> None:
        provider = get_provider("github")
        assert isinstance(provider, GitHubProvider)

    def test_get_provider_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown OAuth provider"):
            get_provider("myspace")


class TestAuthorizationUrls:
    """Test that each provider generates a valid authorization URL with PKCE + state."""

    def test_google_url_contains_required_params(self) -> None:
        provider = GoogleProvider()
        url, verifier = provider.get_authorization_url("http://localhost/callback", "test-state")
        assert "accounts.google.com" in url
        assert "state=test-state" in url
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert len(verifier) > 0

    def test_apple_url_contains_required_params(self) -> None:
        provider = AppleProvider()
        url, verifier = provider.get_authorization_url("http://localhost/callback", "test-state")
        assert "appleid.apple.com" in url
        assert "state=test-state" in url
        assert "code_challenge=" in url
        assert len(verifier) > 0

    def test_facebook_url_contains_required_params(self) -> None:
        provider = FacebookProvider()
        url, verifier = provider.get_authorization_url("http://localhost/callback", "test-state")
        assert "facebook.com" in url
        assert "state=test-state" in url
        assert "code_challenge=" in url
        assert len(verifier) > 0

    def test_github_url_contains_required_params(self) -> None:
        provider = GitHubProvider()
        url, verifier = provider.get_authorization_url("http://localhost/callback", "test-state")
        assert "github.com" in url
        assert "state=test-state" in url
        assert "code_challenge=" in url
        assert len(verifier) > 0

    def test_verifier_differs_between_calls(self) -> None:
        provider = GoogleProvider()
        _, v1 = provider.get_authorization_url("http://localhost/callback", "s1")
        _, v2 = provider.get_authorization_url("http://localhost/callback", "s2")
        assert v1 != v2


class TestPKCEVerifierStorage:
    """Test PKCE verifier persistence (#236)."""

    def test_store_and_retrieve_in_memory(self) -> None:
        with patch("src.auth.providers.get_redis_client", return_value=None):
            store_pkce_verifier("state-abc", "verifier-xyz")
            result = retrieve_pkce_verifier("state-abc")
            assert result == "verifier-xyz"

    def test_retrieve_deletes_verifier(self) -> None:
        with patch("src.auth.providers.get_redis_client", return_value=None):
            store_pkce_verifier("state-del", "verifier-del")
            retrieve_pkce_verifier("state-del")
            result = retrieve_pkce_verifier("state-del")
            assert result is None

    def test_retrieve_missing_returns_none(self) -> None:
        with patch("src.auth.providers.get_redis_client", return_value=None):
            result = retrieve_pkce_verifier("nonexistent")
            assert result is None

    def test_store_uses_redis_when_available(self) -> None:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("src.auth.providers.get_redis_client", return_value=mock_redis):
            store_pkce_verifier("state-redis", "verifier-redis")

        mock_redis.setex.assert_called_once_with("pkce:state-redis", 600, "verifier-redis")

    def test_retrieve_uses_redis_when_available(self) -> None:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = ["verifier-redis", 1]

        with patch("src.auth.providers.get_redis_client", return_value=mock_redis):
            result = retrieve_pkce_verifier("state-redis")

        assert result == "verifier-redis"
        mock_pipe.get.assert_called_once_with("pkce:state-redis")
        mock_pipe.delete.assert_called_once_with("pkce:state-redis")

    def test_falls_back_to_memory_on_redis_failure(self) -> None:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.setex.side_effect = OSError("Connection lost")

        with patch("src.auth.providers.get_redis_client", return_value=mock_redis):
            store_pkce_verifier("state-fallback", "verifier-fallback")

        entry = _pkce_store.get("state-fallback")
        assert entry is not None
        assert entry[0] == "verifier-fallback"


class TestOAuthRedirectURI:
    """Test configurable OAuth redirect URI (#237)."""

    def test_redirect_uri_uses_settings(self) -> None:
        from src.api.routes.auth import _build_redirect_uri

        uri = _build_redirect_uri("google")
        assert uri == "http://localhost:8000/api/v1/auth/callback/google"

    def test_redirect_uri_strips_trailing_slash(self) -> None:
        from src.api.routes.auth import _build_redirect_uri
        from src.config import AuthSettings

        mock_settings = MagicMock()
        mock_auth = AuthSettings(
            _env_file=None,
            jwt_secret="test",
            oauth_redirect_base_url="https://example.com/",
        )
        mock_settings.auth = mock_auth

        with patch("src.api.routes.auth.get_settings", return_value=mock_settings):
            uri = _build_redirect_uri("github")
        assert uri == "https://example.com/api/v1/auth/callback/github"


class TestAppleJWKS:
    """Test Apple ID token JWKS verification (#238)."""

    @pytest.mark.asyncio
    async def test_get_apple_jwks_caches_result(self) -> None:
        import src.auth.providers as prov

        prov._apple_jwks_cache = None
        prov._apple_jwks_fetched_at = 0.0

        fake_jwks = {"keys": [{"kty": "RSA", "kid": "test-key"}]}
        mock_resp = MagicMock()
        mock_resp.json.return_value = fake_jwks
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.auth.providers.httpx.AsyncClient", return_value=mock_client):
            result1 = await prov._get_apple_jwks()
            result2 = await prov._get_apple_jwks()

        assert result1 == fake_jwks
        assert result2 == fake_jwks
        mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_apple_jwks_cache_expires(self) -> None:
        import time

        import src.auth.providers as prov

        fake_jwks = {"keys": [{"kty": "RSA", "kid": "test-key"}]}
        prov._apple_jwks_cache = fake_jwks
        prov._apple_jwks_fetched_at = time.monotonic() - 90000

        new_jwks = {"keys": [{"kty": "RSA", "kid": "new-key"}]}
        mock_resp = MagicMock()
        mock_resp.json.return_value = new_jwks
        mock_resp.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.auth.providers.httpx.AsyncClient", return_value=mock_client):
            result = await prov._get_apple_jwks()

        assert result == new_jwks
        mock_client.get.assert_called_once()
