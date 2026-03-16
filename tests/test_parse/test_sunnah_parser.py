"""End-to-end tests for the Sunnah.com API parser."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from src.parse.schemas import COLLECTION_SCHEMA, HADITH_SCHEMA
from src.parse.sunnah_api import run


def _make_sunnah_data(raw_dir: Path) -> None:
    """Create minimal Sunnah.com raw JSON test data."""
    sunnah_dir = raw_dir / "sunnah"
    sunnah_dir.mkdir(parents=True)

    collections = [
        {
            "name": "bukhari",
            "title": "Sahih al-Bukhari",
            "totalHadith": 2,
        },
    ]
    (sunnah_dir / "collections.json").write_text(json.dumps(collections), encoding="utf-8")

    hadiths = [
        {
            "hadithNumber": 1,
            "bookNumber": 1,
            "chapterNumber": 1,
            "hadith": [
                {"lang": "ar", "body": "نص الحديث بالعربية"},
                {"lang": "en", "body": "Hadith text in English"},
            ],
            "grades": [{"grade": "Sahih"}],
            "chapterTitle": "Revelation",
        },
        {
            "hadithNumber": 2,
            "bookNumber": 1,
            "chapterNumber": 1,
            "hadith": [
                {"lang": "en", "body": "Second hadith text"},
            ],
        },
    ]
    (sunnah_dir / "bukhari_hadiths.json").write_text(json.dumps(hadiths), encoding="utf-8")


class TestSunnahParser:
    def test_produces_parquet_files(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_sunnah_data(raw_dir)

        output_files = run(raw_dir, staging_dir)

        assert len(output_files) == 2
        assert all(p.exists() for p in output_files)

    def test_hadith_schema_conforms(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_sunnah_data(raw_dir)

        run(raw_dir, staging_dir)

        table = pq.read_table(staging_dir / "hadiths_sunnah.parquet")
        assert table.schema == HADITH_SCHEMA
        assert table.num_rows == 2

    def test_collection_schema_conforms(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_sunnah_data(raw_dir)

        run(raw_dir, staging_dir)

        table = pq.read_table(staging_dir / "collections_sunnah.parquet")
        assert table.schema == COLLECTION_SCHEMA
        assert table.num_rows == 1

    def test_skips_when_no_raw_data(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        (raw_dir / "sunnah").mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        output_files = run(raw_dir, staging_dir)

        assert output_files == []

    def test_source_corpus_field(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_sunnah_data(raw_dir)

        run(raw_dir, staging_dir)

        table = pq.read_table(staging_dir / "hadiths_sunnah.parquet")
        corpora = table.column("source_corpus").to_pylist()
        assert all(c == "sunnah" for c in corpora)
