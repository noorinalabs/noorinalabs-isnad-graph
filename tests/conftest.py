"""Shared fixtures for the isnad-graph test suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn
from unittest.mock import patch

import pytest

from src.config import Neo4jSettings, PostgresSettings, RedisSettings, Settings, get_settings
from src.models.enums import (
    ChainClassification,
    Gender,
    HadithGrade,
    NarratorGeneration,
    SectAffiliation,
    SourceCorpus,
    TrustworthinessGrade,
)
from src.models.hadith import Hadith
from src.models.narrator import Narrator


@pytest.fixture(autouse=True)
def _offline_external_clients(request: pytest.FixtureRequest) -> Iterator[None]:
    """Make Redis/Postgres probes fail fast so the unit tier runs offline (ig#1113).

    Tests that spin up the FastAPI app (``test_api`` / ``test_auth`` /
    ``test_security``) route requests through code that opens real sockets to
    backing services when the app isn't fully mocked:

    * ``RateLimitMiddleware._get_redis`` → ``redis.Redis.from_url(...).ping()``
      on ``redis://localhost:6379`` (per app instance);
    * the ``/health`` (and ``/status``) routes → ``PgClient()`` →
      ``psycopg.connect`` on ``localhost:5432`` and ``get_redis_client`` →
      ``redis.Redis.from_url(...).ping()``.

    With no service running this fast-fails in CI (loopback ``ECONNREFUSED`` →
    the routes/middleware degrade gracefully), but in a blackhole-connect
    sandbox each ``connect()`` stalls for the full socket timeout, hanging the
    offline unit run. Forcing the two client constructors to raise immediately
    reproduces CI's fast-fail deterministically: the rate limiter falls back to
    its in-memory window, the health checks report the service ``down`` (503),
    and no socket is ever opened. This is exactly the degradation those code
    paths already document and the unit tier already relies on.

    Tests that exercise these clients directly (e.g.
    ``test_security/test_rate_limiting.py`` or ``test_api/test_health.py``)
    re-patch ``redis.Redis.from_url`` / ``health.PgClient`` in their own
    ``with`` block, which transparently overrides this autouse patch for their
    scope. Integration/e2e tests opt out so they retain real client wiring
    against their testcontainers / live services.
    """
    if request.node.get_closest_marker("integration") or request.node.get_closest_marker("e2e"):
        yield
        return

    def _refuse_redis(*_args: object, **_kwargs: object) -> NoReturn:
        import redis

        raise redis.exceptions.ConnectionError("Redis disabled in offline unit tier (ig#1113)")

    def _refuse_postgres(*_args: object, **_kwargs: object) -> NoReturn:
        import psycopg

        raise psycopg.OperationalError("Postgres disabled in offline unit tier (ig#1113)")

    with (
        patch("redis.Redis.from_url", side_effect=_refuse_redis),
        patch("psycopg.connect", side_effect=_refuse_postgres),
    ):
        yield


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Settings with test defaults via env vars."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "console")
    # Clear lru_cache so fresh settings are created
    get_settings.cache_clear()
    # Nested settings models must be constructed explicitly since they have
    # their own env_prefix and default values baked in at class level.
    return Settings(
        neo4j=Neo4jSettings(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="test_password",
        ),
        postgres=PostgresSettings(dsn="postgresql://test:test@localhost:5432/test"),
        redis=RedisSettings(url="redis://localhost:6379/0"),
    )


@pytest.fixture
def sample_narrator() -> Narrator:
    """A minimal valid Narrator instance for testing."""
    return Narrator(
        id="nar:abu-hurayra-001",
        name_ar="أبو هريرة",
        name_en="Abu Hurayra",
        generation=NarratorGeneration.SAHABI,
        gender=Gender.MALE,
        sect_affiliation=SectAffiliation.SUNNI,
        trustworthiness_consensus=TrustworthinessGrade.THIQA,
    )


@pytest.fixture
def sample_hadith() -> Hadith:
    """A minimal valid Hadith instance for testing."""
    return Hadith(
        id="hdt:bukhari-001-001",
        matn_ar="إنما الأعمال بالنيات",
        source_corpus=SourceCorpus.SUNNAH,
    )


@pytest.fixture
def sample_grading_data() -> dict[str, object]:
    """Raw data dict for building a Grading instance."""
    return {
        "id": "grading-001",
        "hadith_id": "hdt:bukhari-001-001",
        "scholar_name": "Al-Bukhari",
        "grade": HadithGrade.SAHIH,
    }


@pytest.fixture
def sample_chain_data() -> dict[str, object]:
    """Raw data dict for building a Chain instance."""
    return {
        "id": "chn:bukhari-001-001-0",
        "hadith_id": "hdt:bukhari-001-001",
        "chain_index": 0,
        "chain_length": 3,
        "is_complete": True,
        "classification": ChainClassification.MUTTASIL,
        "narrator_ids": ["nar:narrator-a", "nar:narrator-b", "nar:narrator-c"],
    }


@pytest.fixture
def tmp_raw_dir(tmp_path: Path) -> Path:
    """Create and return a temporary 'raw' directory."""
    d = tmp_path / "raw"
    d.mkdir()
    return d


@pytest.fixture
def tmp_staging_dir(tmp_path: Path) -> Path:
    """Create and return a temporary 'staging' directory."""
    d = tmp_path / "staging"
    d.mkdir()
    return d
