"""Application configuration via Pydantic Settings, loaded from .env."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Neo4jSettings(BaseSettings):
    """Neo4j graph database connection settings."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "isnad_graph_dev"

    model_config = SettingsConfigDict(env_prefix="NEO4J_")


class PostgresSettings(BaseSettings):
    """PostgreSQL connection settings.

    The preferred config path is the separate component vars below
    (PG_HOST/PORT/USER/PASSWORD/DB). When PG_HOST is set, the DSN is built
    in-app with the user and password percent-encoded via ``urllib.parse.quote``
    — so a password containing URL-reserved characters (`/`, `+`, `=`, `@`, `:`,
    `#`, ...) can never corrupt the URL authority and break ``urlparse`` at
    startup (#956, sibling of user-service #65). PG_DSN is retained as a
    backward-compatible fallback and as the local-dev default; it is used
    verbatim only when PG_HOST is unset. Consumers should read
    :attr:`effective_dsn`, never ``dsn`` directly.
    """

    dsn: str = "postgresql://isnad:isnad_dev@localhost:5432/isnad_graph"
    host: str | None = None
    port: int = 5432
    user: str | None = None
    password: str | None = None
    db: str | None = None
    # Scheme used when building the DSN from components.
    driver: str = "postgresql"

    model_config = SettingsConfigDict(env_prefix="PG_")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_dsn(self) -> str:
        """The Postgres DSN the app should actually connect with.

        When ``host`` is set, build the DSN from the component vars with the
        user and password percent-encoded (``safe=""`` so every URL-reserved
        character is escaped), so a password with URL-unsafe characters can
        never corrupt the URL. Otherwise fall back to ``dsn`` verbatim
        (backward compat / local-dev default).
        """
        if self.host is None:
            return self.dsn
        auth = ""
        if self.user is not None:
            auth = quote(self.user, safe="")
            if self.password is not None:
                auth += f":{quote(self.password, safe='')}"
            auth += "@"
        path = f"/{self.db}" if self.db is not None else ""
        return f"{self.driver}://{auth}{self.host}:{self.port}{path}"


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""

    requests_per_minute: int = 120
    window_seconds: int = 60

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_")


class RedisSettings(BaseSettings):
    """Redis cache connection settings.

    The preferred config path is the separate component vars below
    (REDIS_HOST/PORT/PASSWORD/DB, + REDIS_TLS). When REDIS_HOST is set, the URL
    is built in-app with the password percent-encoded via ``urllib.parse.quote``
    — so a base64 password containing `/` no longer terminates the URL authority
    and crashes ``urlparse`` at startup (#956, sibling of user-service #65).
    REDIS_URL is the backward-compatible fallback / local-dev default, used
    verbatim only when REDIS_HOST is unset. Consumers should read
    :attr:`effective_url`, never ``url`` directly.
    """

    url: str = "redis://localhost:6379/0"
    host: str | None = None
    port: int = 6379
    password: str | None = None
    db: int = 0
    # Set true to use rediss:// (TLS) when building the URL from components.
    tls: bool = False

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_url(self) -> str:
        """The Redis connection URL the app should actually connect with.

        When ``host`` is set, build ``redis(s)://[:<encoded-password>@]host:port/db``
        with the password percent-encoded via ``urllib.parse.quote`` (``safe=""``
        so `/`, `@`, `:`, `#`, etc. survive ``urlparse``). Otherwise fall back to
        ``url`` verbatim (backward compat / local-dev default).
        """
        if self.host is None:
            return self.url
        scheme = "rediss" if self.tls else "redis"
        auth = ""
        if self.password:
            auth = f":{quote(self.password, safe='')}@"
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"


class AuthSettings(BaseSettings):
    """Authentication settings for user-service JWT validation."""

    user_service_url: str = "http://localhost:8001"
    user_service_jwks_cache_ttl: int = 3600
    session_idle_timeout_minutes: int = 30
    session_idle_warning_seconds: int = 60
    max_concurrent_sessions: int = 5

    model_config = SettingsConfigDict(env_prefix="AUTH_")


class SecurityHeaderSettings(BaseSettings):
    """Configurable security headers. Production defaults; override for dev."""

    content_security_policy: str = "default-src 'self'; frame-ancestors 'none'"
    hsts_max_age: int = 63072000
    hsts_include_subdomains: bool = True
    hsts_preload: bool = True
    x_frame_options: str = "DENY"
    x_xss_protection: str = "0"
    referrer_policy: str = "strict-origin-when-cross-origin"
    permissions_policy: str = (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"
    )
    cross_origin_opener_policy: str = "same-origin"
    cross_origin_resource_policy: str = "same-origin"

    model_config = SettingsConfigDict(env_prefix="SECURITY_")


class LokiSettings(BaseSettings):
    """Loki log-retention runtime override (ig#1038 / deploy#451).

    Path to the hot-reloadable Loki ``runtime_config`` overrides file. The admin
    "log retention (days)" control rewrites ``overrides.<tenant>.retention_period``
    in this file in place; Loki re-reads it every ``runtime_config.period`` (30s)
    with no restart. On the VPS this is the ``loki_runtime`` volume mounted into
    the api container at ``/etc/loki/runtime``; absent in local/dev (the write is
    then a no-op and the DB-persisted value remains the source of truth).
    """

    runtime_overrides_path: str = "/etc/loki/runtime/overrides.yaml"

    model_config = SettingsConfigDict(env_prefix="LOKI_")


class Settings(BaseSettings):
    """Root application settings, composed from nested service settings."""

    neo4j: Neo4jSettings = Neo4jSettings()
    postgres: PostgresSettings = PostgresSettings()
    redis: RedisSettings = RedisSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    auth: AuthSettings = AuthSettings()
    security_headers: SecurityHeaderSettings = SecurityHeaderSettings()
    loki: LokiSettings = LokiSettings()

    cors_origins: list[str] = ["http://localhost:3000"]

    log_level: str = "INFO"
    log_format: str = "console"

    # Semantic-search embedding model. The default ``"hashing"`` selects the
    # dependency-free encoder (CI / sandbox / local dev); production sets this to
    # a real sentence-transformers model name on the cluster (P5W4 load). See
    # ``src/enrich/embeddings.py``. Read via env ``EMBEDDING_MODEL``.
    embedding_model: str = "hashing"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
