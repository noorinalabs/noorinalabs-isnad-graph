"""Application configuration via Pydantic Settings, loaded from .env."""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Neo4jSettings(BaseSettings):
    """Neo4j graph database connection settings."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "isnad_graph_dev"

    model_config = SettingsConfigDict(env_prefix="NEO4J_")


class PostgresSettings(BaseSettings):
    """PostgreSQL connection settings."""

    dsn: str = "postgresql://isnad:isnad_dev@localhost:5432/isnad_graph"

    model_config = SettingsConfigDict(env_prefix="PG_")


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""

    requests_per_minute: int = 120
    window_seconds: int = 60
    trusted_proxies: str = "127.0.0.1,::1,172.16.0.0/12,10.0.0.0/8"

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_")


class RedisSettings(BaseSettings):
    """Redis cache connection settings."""

    url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_prefix="REDIS_")


_JWT_WEAK_DEFAULT = "dev-secret-change-in-production"


class AuthSettings(BaseSettings):
    """OAuth and JWT authentication settings."""

    jwt_secret: str = _JWT_WEAK_DEFAULT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cookie_secure: bool = True
    google_client_id: str = ""
    google_client_secret: str = ""
    apple_client_id: str = ""
    apple_client_secret: str = ""
    facebook_client_id: str = ""
    facebook_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(env_prefix="AUTH_")

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> AuthSettings:
        """Reject weak JWT secrets in production environments."""
        # Import here to avoid circular dependency; environment is on the root Settings,
        # but AuthSettings is constructed standalone too. We read the env var directly.
        import os

        environment = os.environ.get("ENVIRONMENT", "production").lower()
        is_dev = environment in {"dev", "development", "test", "testing"}

        if self.jwt_secret == _JWT_WEAK_DEFAULT:
            if is_dev:
                generated = secrets.token_urlsafe(32)
                object.__setattr__(self, "jwt_secret", generated)
                logger.warning(
                    "JWT secret was the insecure default — generated a random secret for %s. "
                    "Set AUTH_JWT_SECRET in .env for stable tokens across restarts.",
                    environment,
                )
            else:
                raise ValueError(
                    "AUTH_JWT_SECRET must be explicitly set in production. "
                    "The default value is not allowed outside dev/test environments."
                )
        elif len(self.jwt_secret) < 32:
            if not is_dev:
                raise ValueError(
                    f"AUTH_JWT_SECRET must be at least 32 characters in production "
                    f"(got {len(self.jwt_secret)}). Generate one with: "
                    f'python -c "import secrets; print(secrets.token_urlsafe(32))"'
                )
        return self


class SecurityHeaderSettings(BaseSettings):
    """Configurable security headers. Production defaults; override for dev."""

    content_security_policy: str = "default-src 'self'"
    hsts_max_age: int = 63072000
    hsts_include_subdomains: bool = True
    x_frame_options: str = "DENY"
    referrer_policy: str = "strict-origin-when-cross-origin"
    permissions_policy: str = "camera=(), microphone=(), geolocation=()"

    model_config = SettingsConfigDict(env_prefix="SECURITY_")


class Settings(BaseSettings):
    """Root application settings, composed from nested service settings."""

    environment: str = "production"

    neo4j: Neo4jSettings = Neo4jSettings()
    postgres: PostgresSettings = PostgresSettings()
    redis: RedisSettings = RedisSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    auth: AuthSettings = AuthSettings()
    security_headers: SecurityHeaderSettings = SecurityHeaderSettings()

    sunnah_api_key: str = ""
    kaggle_username: str = ""
    kaggle_key: str = ""

    data_raw_dir: Path = Path("./data/raw")
    data_staging_dir: Path = Path("./data/staging")
    data_curated_dir: Path = Path("./data/curated")

    topic_labels: list[str] = [
        "theology",
        "jurisprudence",
        "eschatology",
        "succession/imamate",
        "ritual/worship",
        "ethics/conduct",
        "history/sira",
        "commerce/trade",
        "warfare/jihad",
        "family_law",
        "food/drink",
        "medicine",
        "dreams/visions",
        "end_times",
    ]

    cors_origins: list[str] = ["http://localhost:3000"]

    log_level: str = "INFO"
    log_format: str = "console"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
