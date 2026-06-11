"""Tests for application configuration (src.config)."""

from __future__ import annotations

from urllib.parse import unquote, urlparse

import pytest

from src.config import (
    Neo4jSettings,
    PostgresSettings,
    RedisSettings,
    Settings,
    get_settings,
)

# Passwords exercising every URL-reserved character that breaks naive
# string-interpolation + urlparse — the bug class behind #956 / user-service #65.
# The base64-style `tW/3+x=` value is the real us#65 prod-crash repro shape.
URL_HOSTILE_PASSWORDS = [
    "tW/3+x=",  # the us#65 repro: leading `/` terminates the URL authority
    "p@ss/w+rd=",
    "a:b@c/d",
    "with#hash?q",
    "100%done",
    "sl/ash",
]


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


class TestSettingsEnvOverride:
    """Environment variables override Settings fields."""

    def test_override_neo4j_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NEO4J_PASSWORD", "supersecret")
        get_settings.cache_clear()
        # Neo4jSettings reads NEO4J_PASSWORD via its own env_prefix
        neo4j = Neo4jSettings()
        assert neo4j.password == "supersecret"

    def test_postgres_component_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # PG_HOST/USER/PASSWORD/DB are read via the PG_ env_prefix and build the DSN.
        monkeypatch.setenv("PG_HOST", "pg.internal")
        monkeypatch.setenv("PG_USER", "isnad")
        monkeypatch.setenv("PG_PASSWORD", "tW/3+x=")  # URL-hostile
        monkeypatch.setenv("PG_DB", "isnad_graph")
        pg = PostgresSettings()
        parsed = urlparse(pg.effective_dsn)
        assert parsed.hostname == "pg.internal"
        assert parsed.password is not None
        assert unquote(parsed.password) == "tW/3+x="

    def test_redis_component_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REDIS_HOST", "redis.internal")
        monkeypatch.setenv("REDIS_PASSWORD", "tW/3+x=")  # URL-hostile
        monkeypatch.setenv("REDIS_DB", "2")
        r = RedisSettings()
        parsed = urlparse(r.effective_url)
        assert parsed.hostname == "redis.internal"
        assert parsed.path == "/2"
        assert parsed.password is not None
        assert unquote(parsed.password) == "tW/3+x="


class TestPostgresEffectiveDsn:
    """PostgresSettings.effective_dsn — component build vs. pre-built fallback (#956)."""

    def test_falls_back_to_dsn_when_host_unset(self) -> None:
        pg = PostgresSettings(dsn="postgresql://test:test@localhost:5432/test")
        assert pg.effective_dsn == "postgresql://test:test@localhost:5432/test"

    def test_component_form_takes_precedence_over_prebuilt_dsn(self) -> None:
        pg = PostgresSettings(
            dsn="postgresql://ignored:ignored@ignored:9999/ignored",
            host="pg.internal",
            port=5432,
            user="isnad",
            password="isnad_dev",
            db="isnad_graph",
        )
        assert pg.effective_dsn == "postgresql://isnad:isnad_dev@pg.internal:5432/isnad_graph"

    def test_custom_driver_scheme(self) -> None:
        pg = PostgresSettings(
            host="pg.internal", user="u", password="p", db="d", driver="postgresql+psycopg"
        )
        assert pg.effective_dsn.startswith("postgresql+psycopg://")

    def test_host_only_no_credentials(self) -> None:
        pg = PostgresSettings(host="pg.internal", port=5432, db="isnad_graph")
        assert pg.effective_dsn == "postgresql://pg.internal:5432/isnad_graph"

    @pytest.mark.parametrize("password", URL_HOSTILE_PASSWORDS)
    def test_special_char_password_round_trips(self, password: str) -> None:
        pg = PostgresSettings(
            host="pg.internal",
            port=5432,
            user="isnad",
            password=password,
            db="isnad_graph",
        )
        parsed = urlparse(pg.effective_dsn)
        # The special chars must NOT corrupt the authority — host/port parse cleanly.
        assert parsed.hostname == "pg.internal"
        assert parsed.port == 5432
        assert parsed.path == "/isnad_graph"
        assert parsed.username == "isnad"
        # The raw password survives a round-trip back out of the URL.
        assert parsed.password is not None
        assert unquote(parsed.password) == password

    @pytest.mark.parametrize("user", ["us+er", "a/b", "u@h"])
    def test_special_char_username_round_trips(self, user: str) -> None:
        pg = PostgresSettings(host="pg.internal", user=user, password="p", db="d")
        parsed = urlparse(pg.effective_dsn)
        assert parsed.hostname == "pg.internal"
        assert parsed.username is not None
        assert unquote(parsed.username) == user


class TestRedisEffectiveUrl:
    """RedisSettings.effective_url — component build vs. pre-built fallback (#956)."""

    def test_falls_back_to_url_when_host_unset(self) -> None:
        r = RedisSettings(url="redis://localhost:6379/0")
        assert r.effective_url == "redis://localhost:6379/0"

    def test_component_form_takes_precedence_over_prebuilt_url(self) -> None:
        r = RedisSettings(
            url="redis://ignored:1111/9",
            host="redis.internal",
            port=6379,
            password="cachepw",
            db=2,
        )
        assert r.effective_url == "redis://:cachepw@redis.internal:6379/2"

    def test_no_password_omits_auth(self) -> None:
        r = RedisSettings(host="redis.internal", port=6379, db=0)
        assert r.effective_url == "redis://redis.internal:6379/0"

    def test_tls_uses_rediss_scheme(self) -> None:
        r = RedisSettings(host="redis.internal", tls=True)
        assert r.effective_url.startswith("rediss://")

    @pytest.mark.parametrize("password", URL_HOSTILE_PASSWORDS)
    def test_special_char_password_round_trips(self, password: str) -> None:
        r = RedisSettings(host="redis.internal", port=6379, password=password, db=0)
        parsed = urlparse(r.effective_url)
        # The first `/` in a base64 password used to terminate the authority and
        # make urlparse read the next chars as host:port and crash (#65/#956).
        assert parsed.hostname == "redis.internal"
        assert parsed.port == 6379
        assert parsed.path == "/0"
        assert parsed.password is not None
        assert unquote(parsed.password) == password


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
