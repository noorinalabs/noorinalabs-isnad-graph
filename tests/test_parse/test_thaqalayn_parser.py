"""End-to-end tests for the Thaqalayn parser."""

from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq

from src.parse.schemas import COLLECTION_SCHEMA, HADITH_SCHEMA
from src.parse.thaqalayn import run


def _make_thaqalayn_json(raw_dir: Path) -> None:
    """Create minimal Thaqalayn API-format JSON test data."""
    thaq_dir = raw_dir / "thaqalayn"
    thaq_dir.mkdir(parents=True)

    data = {
        "bookName": "Al-Kafi",
        "bookNameAr": "الكافي",
        "data": [
            {
                "hadithNumber": 1,
                "textAr": "نص الحديث الأول",
                "textEn": "First hadith text",
                "grade": "Sahih",
                "chapterEn": "Chapter One",
                "chapterNumber": 1,
            },
            {
                "hadithNumber": 2,
                "textAr": "نص الحديث الثاني",
                "textEn": "Second hadith text",
                "grade": "Hasan",
                "chapterEn": "Chapter One",
                "chapterNumber": 1,
            },
        ],
    }
    (thaq_dir / "book_1.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TestThaqalaynParser:
    def test_produces_parquet_files(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_thaqalayn_json(raw_dir)

        hadiths_path, collections_path = run(raw_dir, staging_dir)

        assert hadiths_path.exists()
        assert collections_path.exists()

    def test_hadith_schema_conforms(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_thaqalayn_json(raw_dir)

        hadiths_path, _ = run(raw_dir, staging_dir)

        table = pq.read_table(hadiths_path)
        assert table.schema == HADITH_SCHEMA
        assert table.num_rows == 2

    def test_collection_schema_conforms(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_thaqalayn_json(raw_dir)

        _, collections_path = run(raw_dir, staging_dir)

        table = pq.read_table(collections_path)
        assert table.schema == COLLECTION_SCHEMA
        assert table.num_rows >= 1

    def test_sect_is_shia(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_thaqalayn_json(raw_dir)

        hadiths_path, _ = run(raw_dir, staging_dir)

        table = pq.read_table(hadiths_path)
        sects = table.column("sect").to_pylist()
        assert all(s == "shia" for s in sects)
