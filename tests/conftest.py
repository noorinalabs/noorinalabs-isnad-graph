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


@pytest.fixture
def sample_staging_hadiths(tmp_path: Path) -> Path:
    """Create mock hadiths_*.parquet files in a staging dir and return the dir path."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    from src.parse.schemas import HADITH_SCHEMA

    staging = tmp_path / "staging"
    staging.mkdir(exist_ok=True)

    rows = {
        "source_id": pa.array(["h-1", "h-2", "h-3"], type=pa.string()),
        "source_corpus": pa.array(["sunnah", "sunnah", "thaqalayn"], type=pa.string()),
        "collection_name": pa.array(["bukhari", "bukhari", "al-kafi"], type=pa.string()),
        "book_number": pa.array([1, 1, 1], type=pa.int32()),
        "chapter_number": pa.array([1, 2, 1], type=pa.int32()),
        "hadith_number": pa.array([1, 2, 1], type=pa.int32()),
        "matn_ar": pa.array(
            ["إنما الأعمال بالنيات", "من حسن إسلام المرء", "إنما الأعمال بالنيات"],
            type=pa.string(),
        ),
        "matn_en": pa.array(
            [
                "Actions are judged by intentions",
                "Part of the perfection of Islam",
                "Actions are judged by intentions",
            ],
            type=pa.string(),
        ),
        "isnad_raw_ar": pa.array(
            ["حدثنا محمد عن علي", "حدثنا أنس عن مالك", None],
            type=pa.string(),
        ),
        "isnad_raw_en": pa.array(
            [
                "Narrated Abu Hurayra from the Prophet",
                "Narrated Anas from Malik",
                None,
            ],
            type=pa.string(),
        ),
        "full_text_ar": pa.array([None, None, "حدثنا أبو هريرة"], type=pa.string()),
        "full_text_en": pa.array([None, None, None], type=pa.string()),
        "grade": pa.array(["sahih", "hasan", None], type=pa.string()),
        "chapter_name_ar": pa.array([None, None, None], type=pa.string()),
        "chapter_name_en": pa.array([None, None, None], type=pa.string()),
        "sect": pa.array(["sunni", "sunni", "shia"], type=pa.string()),
    }
    table = pa.table(rows, schema=HADITH_SCHEMA)
    pq.write_table(table, staging / "hadiths_sunnah.parquet")
    return staging


@pytest.fixture
def sample_narrator_mentions(tmp_path: Path) -> Path:
    """Create mock narrator_mentions_*.parquet files and return the dir path."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    from src.parse.schemas import NARRATOR_MENTION_SCHEMA

    staging = tmp_path / "staging"
    staging.mkdir(exist_ok=True)

    rows = {
        "mention_id": pa.array(["m-1", "m-2", "m-3"], type=pa.string()),
        "source_hadith_id": pa.array(["h-1", "h-1", "h-2"], type=pa.string()),
        "source_corpus": pa.array(["sanadset", "sanadset", "lk"], type=pa.string()),
        "position_in_chain": pa.array([0, 1, 0], type=pa.int32()),
        "name_ar": pa.array(["أبو هريرة", "محمد", "أنس بن مالك"], type=pa.string()),
        "name_en": pa.array(["Abu Hurayra", "Muhammad", "Anas ibn Malik"], type=pa.string()),
        "name_ar_normalized": pa.array(["ابو هريره", "محمد", "انس بن مالك"], type=pa.string()),
        "transmission_method": pa.array(["haddathana", "an", None], type=pa.string()),
    }
    table = pa.table(rows, schema=NARRATOR_MENTION_SCHEMA)
    pq.write_table(table, staging / "narrator_mentions_sanadset.parquet")
    return staging


@pytest.fixture
def sample_narrator_bios(tmp_path: Path) -> Path:
    """Create mock narrators_bio_*.parquet files and return the dir path."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    from src.parse.schemas import NARRATOR_BIO_SCHEMA

    staging = tmp_path / "staging"
    staging.mkdir(exist_ok=True)

    rows = {
        "bio_id": pa.array(["bio-001", "bio-002"], type=pa.string()),
        "source": pa.array(["muhaddithat", "muhaddithat"], type=pa.string()),
        "name_ar": pa.array(["أبو هريرة", "أنس بن مالك"], type=pa.string()),
        "name_en": pa.array(["Abu Hurayra", "Anas ibn Malik"], type=pa.string()),
        "name_ar_normalized": pa.array(["ابو هريره", "انس بن مالك"], type=pa.string()),
        "name_en_normalized": pa.array([None, None], type=pa.string()),
        "kunya": pa.array(["أبو هريرة", None], type=pa.string()),
        "nisba": pa.array([None, None], type=pa.string()),
        "laqab": pa.array([None, None], type=pa.string()),
        "birth_year_ah": pa.array([None, None], type=pa.int32()),
        "death_year_ah": pa.array([59, 93], type=pa.int32()),
        "birth_location": pa.array([None, None], type=pa.string()),
        "death_location": pa.array(["Medina", "Basra"], type=pa.string()),
        "generation": pa.array(["sahabi", "sahabi"], type=pa.string()),
        "gender": pa.array(["male", "male"], type=pa.string()),
        "trustworthiness": pa.array(["thiqa", "thiqa"], type=pa.string()),
        "bio_text": pa.array([None, None], type=pa.string()),
        "external_id": pa.array(["ms-001", None], type=pa.string()),
    }
    table = pa.table(rows, schema=NARRATOR_BIO_SCHEMA)
    pq.write_table(table, staging / "narrators_bio_muhaddithat.parquet")
    return staging


@pytest.fixture
def ml_available() -> bool:
    """Check if sentence-transformers is importable."""
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


@pytest.fixture
def sample_lk_csv(tmp_raw_dir: Path) -> Path:
    """Write a 5-row mock CSV in LK 16-column format, return the file path."""
    from src.parse.lk_corpus import LK_COLUMNS

    lk_dir = tmp_raw_dir / "lk"
    lk_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        [
            "1",
            "Revelation",
            "الوحي",
            "1",
            "Beginning",
            "بدء الوحي",
            str(i),
            "Full English text",
            "Narrated Abu Hurayra: The Prophet said",
            "Actions are by intentions",
            "النص الكامل",
            "حدثنا أبو هريرة",
            "إنما الأعمال بالنيات",
            "",
            "Sahih",
            "صحيح",
        ]
        for i in range(1, 6)
    ]

    header = ",".join(LK_COLUMNS)
    lines = [header] + [",".join(row) for row in rows]
    csv_path = lk_dir / "albukhari.csv"
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path


@pytest.fixture
def sample_sanadset_csv(tmp_raw_dir: Path) -> Path:
    """Write a mock Sanadset CSV with NAR tags, return the file path."""
    sanadset_dir = tmp_raw_dir / "sanadset"
    sanadset_dir.mkdir(parents=True, exist_ok=True)

    header = "hadith_id,book_id,hadith,grade"
    rows = [
        (
            "1",
            "1",
            "<SANAD><NAR>محمد</NAR> عن <NAR>علي</NAR></SANAD><MATN>متن</MATN>",
            "Sahih",
        ),
        (
            "2",
            "1",
            "<SANAD><NAR>أنس</NAR> عن <NAR>مالك</NAR></SANAD><MATN>متن ثاني</MATN>",
            "Hasan",
        ),
        (
            "3",
            "2",
            "<SANAD>No SANAD</SANAD><MATN>متن ثالث</MATN>",
            "",
        ),
    ]
    lines = [header]
    for r in rows:
        lines.append(f'{r[0]},{r[1]},"{r[2]}",{r[3]}')
    csv_path = sanadset_dir / "hadiths.csv"
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    return csv_path
