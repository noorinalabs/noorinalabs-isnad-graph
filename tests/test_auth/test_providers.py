"""Tests for OAuth provider abstraction."""

from __future__ import annotations

import pytest

from src.auth.providers import (
    PROVIDERS,
    AppleProvider,
    FacebookProvider,
    GitHubProvider,
    GoogleProvider,
    get_provider,
)


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
        url = provider.get_authorization_url("http://localhost/callback", "test-state")
        assert "accounts.google.com" in url
        assert "state=test-state" in url
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url

    def test_apple_url_contains_required_params(self) -> None:
        provider = AppleProvider()
        url = provider.get_authorization_url("http://localhost/callback", "test-state")
        assert "appleid.apple.com" in url
        assert "state=test-state" in url
        assert "code_challenge=" in url

    def test_facebook_url_contains_required_params(self) -> None:
        provider = FacebookProvider()
        url = provider.get_authorization_url("http://localhost/callback", "test-state")
        assert "facebook.com" in url
        assert "state=test-state" in url
        assert "code_challenge=" in url

    def test_github_url_contains_required_params(self) -> None:
        provider = GitHubProvider()
        url = provider.get_authorization_url("http://localhost/callback", "test-state")
        assert "github.com" in url
        assert "state=test-state" in url
        assert "code_challenge=" in url
