"""Shared fixtures for the isnad-graph test suite."""

from __future__ import annotations

from pathlib import Path

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
