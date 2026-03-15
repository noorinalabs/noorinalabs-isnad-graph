"""Tests for application configuration (src.config)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Neo4jSettings, Settings, get_settings


class TestSettingsDefaults:
    """Settings loads with expected default values."""

    def test_neo4j_defaults(self, settings: Settings) -> None:
        # monkeypatched env overrides the defaults
        assert settings.neo4j.uri == "bolt://localhost:7687"
        assert settings.neo4j.user == "neo4j"
        assert settings.neo4j.password == "test_password"

    def test_postgres_default(self, settings: Settings) -> None:
        assert settings.postgres.dsn == "postgresql://test:test@localhost:5432/test"

    def test_redis_default(self, settings: Settings) -> None:
        assert settings.redis.url == "redis://localhost:6379/0"

    def test_log_level(self, settings: Settings) -> None:
        assert settings.log_level == "DEBUG"

    def test_log_format(self, settings: Settings) -> None:
        assert settings.log_format == "console"

    def test_data_dirs_are_paths(self, settings: Settings) -> None:
        assert isinstance(settings.data_raw_dir, Path)
        assert isinstance(settings.data_staging_dir, Path)
        assert isinstance(settings.data_curated_dir, Path)


class TestSettingsEnvOverride:
    """Environment variables override Settings fields."""

    def test_override_sunnah_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUNNAH_API_KEY", "my-secret-key")
        get_settings.cache_clear()
        s = Settings()
        assert s.sunnah_api_key == "my-secret-key"

    def test_override_data_raw_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATA_RAW_DIR", "/tmp/test-raw")
        get_settings.cache_clear()
        s = Settings()
        assert s.data_raw_dir == Path("/tmp/test-raw")

    def test_override_neo4j_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEO4J_PASSWORD", "supersecret")
        get_settings.cache_clear()
        # Neo4jSettings reads NEO4J_PASSWORD via its own env_prefix
        neo4j = Neo4jSettings()
        assert neo4j.password == "supersecret"


class TestGetSettings:
    """get_settings() returns a cached singleton."""

    def test_returns_settings_instance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        get_settings.cache_clear()
        s = get_settings()
        assert isinstance(s, Settings)

    def test_caching(self, monkeypatch: pytest.MonkeyPatch) -> None:
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
