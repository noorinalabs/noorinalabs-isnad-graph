"""Application configuration via Pydantic Settings, loaded from .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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


class RedisSettings(BaseSettings):
    """Redis cache connection settings."""

    url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class Settings(BaseSettings):
    """Root application settings, composed from nested service settings."""

    neo4j: Neo4jSettings = Neo4jSettings()
    postgres: PostgresSettings = PostgresSettings()
    redis: RedisSettings = RedisSettings()

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

    log_level: str = "INFO"
    log_format: str = "console"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
