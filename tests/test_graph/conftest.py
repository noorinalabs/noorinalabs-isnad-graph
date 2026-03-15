"""Shared fixtures for graph loading tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from src.parse.schemas import COLLECTION_SCHEMA, HADITH_SCHEMA, NARRATOR_MENTION_SCHEMA
from src.resolve.schemas import (
    NARRATOR_MENTIONS_RESOLVED_SCHEMA,
    NARRATORS_CANONICAL_SCHEMA,
    PARALLEL_LINKS_SCHEMA,
)


class MockNeo4jClient:
    """Records calls instead of hitting a real Neo4j instance."""

    def __init__(self, *, nodes_created_per_batch: int = 0) -> None:
        self.calls: list[tuple[str, dict[str, Any] | list[dict[str, Any]]]] = []
        self.constraints_ensured = False
        self._nodes_created = nodes_created_per_batch
        self._read_results: list[dict[str, Any]] = []

    def ensure_constraints(self) -> None:
        self.constraints_ensured = True

    def execute_write_batch(
        self, query: str, batch: list[dict[str, Any]], batch_size: int = 1000
    ) -> int:
        self.calls.append((query, batch))
        return self._nodes_created if self._nodes_created else len(batch)

    def execute_read(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        self.calls.append((query, parameters or {}))
        return self._read_results

    def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        self.calls.append((query, parameters or {}))
        return []

    def set_read_results(self, results: list[dict[str, Any]]) -> None:
        self._read_results = results


@pytest.fixture
def mock_client() -> MockNeo4jClient:
    return MockNeo4jClient()


@pytest.fixture
def staging_dir(tmp_path: Path) -> Path:
    d = tmp_path / "staging"
    d.mkdir()
    return d


@pytest.fixture
def curated_dir(tmp_path: Path) -> Path:
    d = tmp_path / "curated"
    d.mkdir()
    return d


def write_narrators_canonical(staging: Path, rows: list[dict[str, Any]]) -> Path:
    """Write a narrators_canonical.parquet file."""
    arrays = {
        "canonical_id": pa.array([r.get("canonical_id", "") for r in rows], type=pa.string()),
        "name_ar": pa.array([r.get("name_ar") for r in rows], type=pa.string()),
        "name_en": pa.array([r.get("name_en") for r in rows], type=pa.string()),
        "name_ar_normalized": pa.array(
            [r.get("name_ar_normalized") for r in rows], type=pa.string()
        ),
        "aliases": pa.array([r.get("aliases", []) for r in rows], type=pa.list_(pa.string())),
        "birth_year_ah": pa.array([r.get("birth_year_ah") for r in rows], type=pa.int32()),
        "death_year_ah": pa.array([r.get("death_year_ah") for r in rows], type=pa.int32()),
        "generation": pa.array([r.get("generation") for r in rows], type=pa.string()),
        "gender": pa.array([r.get("gender") for r in rows], type=pa.string()),
        "trustworthiness": pa.array([r.get("trustworthiness") for r in rows], type=pa.string()),
        "source_ids": pa.array([r.get("source_ids", []) for r in rows], type=pa.list_(pa.string())),
        "external_id": pa.array([r.get("external_id") for r in rows], type=pa.string()),
        "mention_count": pa.array([r.get("mention_count") for r in rows], type=pa.int32()),
    }
    table = pa.table(arrays, schema=NARRATORS_CANONICAL_SCHEMA)
    path = staging / "narrators_canonical.parquet"
    pq.write_table(table, path)
    return path


def write_hadiths(staging: Path, rows: list[dict[str, Any]], suffix: str = "test") -> Path:
    """Write a hadiths_*.parquet file."""
    arrays = {
        "source_id": pa.array([r["source_id"] for r in rows], type=pa.string()),
        "source_corpus": pa.array(
            [r.get("source_corpus", "sunnah") for r in rows], type=pa.string()
        ),
        "collection_name": pa.array(
            [r.get("collection_name", "bukhari") for r in rows], type=pa.string()
        ),
        "book_number": pa.array([r.get("book_number") for r in rows], type=pa.int32()),
        "chapter_number": pa.array([r.get("chapter_number") for r in rows], type=pa.int32()),
        "hadith_number": pa.array([r.get("hadith_number") for r in rows], type=pa.int32()),
        "matn_ar": pa.array([r.get("matn_ar") for r in rows], type=pa.string()),
        "matn_en": pa.array([r.get("matn_en") for r in rows], type=pa.string()),
        "isnad_raw_ar": pa.array([r.get("isnad_raw_ar") for r in rows], type=pa.string()),
        "isnad_raw_en": pa.array([r.get("isnad_raw_en") for r in rows], type=pa.string()),
        "full_text_ar": pa.array([r.get("full_text_ar") for r in rows], type=pa.string()),
        "full_text_en": pa.array([r.get("full_text_en") for r in rows], type=pa.string()),
        "grade": pa.array([r.get("grade") for r in rows], type=pa.string()),
        "chapter_name_ar": pa.array([r.get("chapter_name_ar") for r in rows], type=pa.string()),
        "chapter_name_en": pa.array([r.get("chapter_name_en") for r in rows], type=pa.string()),
        "sect": pa.array([r.get("sect", "sunni") for r in rows], type=pa.string()),
    }
    table = pa.table(arrays, schema=HADITH_SCHEMA)
    path = staging / f"hadiths_{suffix}.parquet"
    pq.write_table(table, path)
    return path


def write_collections(staging: Path, rows: list[dict[str, Any]], suffix: str = "test") -> Path:
    """Write a collections_*.parquet file."""
    arrays = {
        "collection_id": pa.array([r["collection_id"] for r in rows], type=pa.string()),
        "name_ar": pa.array([r.get("name_ar") for r in rows], type=pa.string()),
        "name_en": pa.array([r.get("name_en", "") for r in rows], type=pa.string()),
        "compiler_name": pa.array([r.get("compiler_name") for r in rows], type=pa.string()),
        "compilation_year_ah": pa.array(
            [r.get("compilation_year_ah") for r in rows], type=pa.int32()
        ),
        "sect": pa.array([r.get("sect", "sunni") for r in rows], type=pa.string()),
        "total_hadiths": pa.array([r.get("total_hadiths") for r in rows], type=pa.int32()),
        "source_corpus": pa.array(
            [r.get("source_corpus", "sunnah") for r in rows], type=pa.string()
        ),
    }
    table = pa.table(arrays, schema=COLLECTION_SCHEMA)
    path = staging / f"collections_{suffix}.parquet"
    pq.write_table(table, path)
    return path


def write_narrator_mentions(
    staging: Path, rows: list[dict[str, Any]], suffix: str = "test"
) -> Path:
    """Write a narrator_mentions_*.parquet file using staging schema."""
    arrays = {
        "mention_id": pa.array([r["mention_id"] for r in rows], type=pa.string()),
        "source_hadith_id": pa.array([r["source_hadith_id"] for r in rows], type=pa.string()),
        "source_corpus": pa.array(
            [r.get("source_corpus", "sanadset") for r in rows], type=pa.string()
        ),
        "position_in_chain": pa.array(
            [r.get("position_in_chain", 0) for r in rows], type=pa.int32()
        ),
        "name_ar": pa.array([r.get("name_ar") for r in rows], type=pa.string()),
        "name_en": pa.array([r.get("name_en") for r in rows], type=pa.string()),
        "name_ar_normalized": pa.array(
            [r.get("name_ar_normalized") for r in rows], type=pa.string()
        ),
        "transmission_method": pa.array(
            [r.get("transmission_method") for r in rows], type=pa.string()
        ),
    }
    table = pa.table(arrays, schema=NARRATOR_MENTION_SCHEMA)
    path = staging / f"narrator_mentions_{suffix}.parquet"
    pq.write_table(table, path)
    return path


def write_narrator_mentions_resolved(
    staging: Path, rows: list[dict[str, Any]], suffix: str = "resolved"
) -> Path:
    """Write a narrator_mentions_resolved*.parquet file."""
    arrays = {
        "mention_id": pa.array([r["mention_id"] for r in rows], type=pa.string()),
        "hadith_id": pa.array([r["hadith_id"] for r in rows], type=pa.string()),
        "source_corpus": pa.array(
            [r.get("source_corpus", "sanadset") for r in rows], type=pa.string()
        ),
        "position_in_chain": pa.array(
            [r.get("position_in_chain", 0) for r in rows], type=pa.int32()
        ),
        "name_raw": pa.array([r.get("name_raw") for r in rows], type=pa.string()),
        "name_normalized": pa.array([r.get("name_normalized") for r in rows], type=pa.string()),
        "canonical_narrator_id": pa.array(
            [r.get("canonical_narrator_id") for r in rows], type=pa.string()
        ),
        "transmission_method": pa.array(
            [r.get("transmission_method") for r in rows], type=pa.string()
        ),
        "confidence": pa.array([r.get("confidence") for r in rows], type=pa.float32()),
    }
    table = pa.table(arrays, schema=NARRATOR_MENTIONS_RESOLVED_SCHEMA)
    path = staging / f"narrator_mentions_{suffix}.parquet"
    pq.write_table(table, path)
    return path


def write_parallel_links(staging: Path, rows: list[dict[str, Any]]) -> Path:
    """Write a parallel_links.parquet file."""
    arrays = {
        "hadith_id_a": pa.array([r["hadith_id_a"] for r in rows], type=pa.string()),
        "hadith_id_b": pa.array([r["hadith_id_b"] for r in rows], type=pa.string()),
        "similarity_score": pa.array(
            [r.get("similarity_score", 0.9) for r in rows], type=pa.float32()
        ),
        "variant_type": pa.array(
            [r.get("variant_type", "wording") for r in rows], type=pa.string()
        ),
        "cross_sect": pa.array([r.get("cross_sect", False) for r in rows], type=pa.bool_()),
    }
    table = pa.table(arrays, schema=PARALLEL_LINKS_SCHEMA)
    path = staging / "parallel_links.parquet"
    pq.write_table(table, path)
    return path


def write_historical_events_yaml(curated: Path, events: list[dict[str, Any]]) -> Path:
    """Write a historical_events.yaml file."""
    path = curated / "historical_events.yaml"
    with open(path, "w") as f:
        yaml.dump({"events": events}, f)
    return path


def write_locations_yaml(curated: Path, locations: list[dict[str, Any]]) -> Path:
    """Write a locations.yaml file."""
    path = curated / "locations.yaml"
    with open(path, "w") as f:
        yaml.dump({"locations": locations}, f)
    return path
