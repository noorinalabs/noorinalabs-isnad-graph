"""End-to-end tests for the Fawaz parser."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from src.parse.fawaz import run
from src.parse.schemas import COLLECTION_SCHEMA, HADITH_SCHEMA


def _make_fawaz_data(raw_dir: Path) -> None:
    """Create minimal Fawaz edition JSON test data."""
    fawaz_dir = raw_dir / "fawaz"
    fawaz_dir.mkdir(parents=True)

    # editions.json catalog
    editions = {"eng-bukhari": {"name": "Sahih al-Bukhari", "collection": "bukhari"}}
    (fawaz_dir / "editions.json").write_text(json.dumps(editions), encoding="utf-8")

    # info.json (can be empty)
    (fawaz_dir / "info.json").write_text(json.dumps({}), encoding="utf-8")

    # Edition file
    edition_data = {
        "metadata": {"name": "Sahih al-Bukhari", "author": "Imam al-Bukhari"},
        "hadiths": [
            {"hadithnumber": 1, "text": "Actions are by intentions", "grades": []},
            {"hadithnumber": 2, "text": "Islam is built on five pillars", "grades": []},
            {"hadithnumber": 3, "text": "None of you truly believes", "grades": []},
        ],
    }
    (fawaz_dir / "eng-bukhari.json").write_text(json.dumps(edition_data), encoding="utf-8")


class TestFawazParser:
    def test_produces_parquet_files(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_fawaz_data(raw_dir)

        hadiths_path, collections_path = run(raw_dir, staging_dir)

        assert hadiths_path.exists()
        assert collections_path.exists()

    def test_hadith_schema_conforms(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_fawaz_data(raw_dir)

        hadiths_path, _ = run(raw_dir, staging_dir)

        table = pq.read_table(hadiths_path)
        assert table.schema == HADITH_SCHEMA
        assert table.num_rows == 3

    def test_collection_schema_conforms(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_fawaz_data(raw_dir)

        _, collections_path = run(raw_dir, staging_dir)

        table = pq.read_table(collections_path)
        assert table.schema == COLLECTION_SCHEMA
        assert table.num_rows == 1

    def test_source_corpus_field(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_fawaz_data(raw_dir)

        hadiths_path, _ = run(raw_dir, staging_dir)

        table = pq.read_table(hadiths_path)
        corpora = table.column("source_corpus").to_pylist()
        assert all(c == "fawaz" for c in corpora)
