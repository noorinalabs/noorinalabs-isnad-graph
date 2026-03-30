"""Tests for the LK Hadith Corpus parser."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from src.parse.lk_corpus import LK_COLUMNS, run
from src.parse.schemas import COLLECTION_SCHEMA, HADITH_SCHEMA, NARRATOR_MENTION_SCHEMA


def _make_lk_csv(path: Path, rows: list[list[str]]) -> Path:
    """Write a mock LK CSV file with the standard 16-column header."""
    header = ",".join(LK_COLUMNS)
    lines = [header]
    for row in rows:
        lines.append(",".join(row))
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _sample_rows() -> list[list[str]]:
    """Return 3 sample rows in 16-column LK format."""
    return [
        [
            "1",  # Chapter_Number
            "Revelation",  # Chapter_English
            "الوحي",  # Chapter_Arabic
            "1",  # Section_Number
            "Beginning of Revelation",  # Section_English
            "بدء الوحي",  # Section_Arabic
            "1",  # Hadith_number
            "Full hadith text in English",  # English_Hadith
            "Narrated Umar ibn al-Khattab: The Prophet said",  # English_Isnad
            "Actions are by intentions",  # English_Matn
            "النص الكامل للحديث",  # Arabic_Hadith
            "حدثنا عمر بن الخطاب",  # Arabic_Isnad
            "إنما الأعمال بالنيات",  # Arabic_Matn
            "",  # Arabic_Comment
            "Sahih",  # English_Grade
            "صحيح",  # Arabic_Grade
        ],
        [
            "1",
            "Revelation",
            "الوحي",
            "2",
            "Section Two",
            "القسم الثاني",
            "2",
            "Another full text",
            "Narrated Abu Hurayra: that he heard",
            "The matn text here",
            "نص آخر",
            "عن أبي هريرة",
            "متن الحديث",
            "",
            "Hasan",
            "",
        ],
        [
            "2",
            "Faith",
            "الإيمان",
            "1",
            "Pillars of Islam",
            "أركان الإسلام",
            "3",
            "Third hadith",
            "",  # No English isnad
            "Third matn",
            "الحديث الثالث",
            "",  # No Arabic isnad
            "المتن الثالث",
            "",
            "",
            "",
        ],
    ]


class TestDeriveCollectionName:
    """Tests for directory-based and filename-based collection name derivation."""

    def test_filename_mapping(self) -> None:
        from src.parse.lk_corpus import _derive_collection_name

        assert _derive_collection_name(Path("data/lk/albukhari.csv")) == "bukhari"
        assert _derive_collection_name(Path("data/lk/altirmidhi.csv")) == "tirmidhi"

    def test_directory_mapping(self) -> None:
        from src.parse.lk_corpus import _derive_collection_name

        assert _derive_collection_name(Path("data/lk/Bukhari/Chapter1.csv")) == "bukhari"
        assert _derive_collection_name(Path("data/lk/Muslim/Chapter3.csv")) == "muslim"
        assert _derive_collection_name(Path("data/lk/AbuDaud/Chapter1.csv")) == "abu_dawud"
        assert _derive_collection_name(Path("data/lk/Tirmizi/Chapter2.csv")) == "tirmidhi"
        assert _derive_collection_name(Path("data/lk/Nesai/Chapter1.csv")) == "nasai"
        assert _derive_collection_name(Path("data/lk/IbnMaja/Chapter5.csv")) == "ibn_majah"

    def test_unknown_returns_none(self) -> None:
        from src.parse.lk_corpus import _derive_collection_name

        assert _derive_collection_name(Path("data/lk/unknown/foo.csv")) is None

    def test_per_chapter_layout_parses(self, tmp_path: Path) -> None:
        """Per-chapter CSVs in book directories should be parsed correctly."""
        raw_dir = tmp_path / "raw"
        lk_dir = raw_dir / "lk" / "Bukhari"
        lk_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        _make_lk_csv(lk_dir / "Chapter1.csv", _sample_rows())

        run(raw_dir, staging_dir)

        table = pq.read_table(staging_dir / "hadiths_lk.parquet")
        assert table.num_rows == 3
        assert all(v.as_py() == "bukhari" for v in table.column("collection_name"))


class TestLkParser:
    def test_produces_parquet_files(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        lk_dir = raw_dir / "lk"
        lk_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        _make_lk_csv(lk_dir / "albukhari.csv", _sample_rows())

        output_paths = run(raw_dir, staging_dir)

        assert any("hadiths_lk.parquet" in str(p) for p in output_paths)
        assert (staging_dir / "hadiths_lk.parquet").exists()
        assert (staging_dir / "collections_lk.parquet").exists()

    def test_hadith_row_count(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        lk_dir = raw_dir / "lk"
        lk_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        rows = _sample_rows()
        _make_lk_csv(lk_dir / "albukhari.csv", rows)
        run(raw_dir, staging_dir)

        table = pq.read_table(staging_dir / "hadiths_lk.parquet")
        assert table.num_rows == len(rows)

    def test_hadith_schema_conforms(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        lk_dir = raw_dir / "lk"
        lk_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        _make_lk_csv(lk_dir / "albukhari.csv", _sample_rows())
        run(raw_dir, staging_dir)

        table = pq.read_table(staging_dir / "hadiths_lk.parquet")
        assert table.schema == HADITH_SCHEMA

    def test_collection_metadata(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        lk_dir = raw_dir / "lk"
        lk_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        _make_lk_csv(lk_dir / "albukhari.csv", _sample_rows())
        run(raw_dir, staging_dir)

        table = pq.read_table(staging_dir / "collections_lk.parquet")
        assert table.schema == COLLECTION_SCHEMA
        assert table.num_rows == 1
        assert table.column("name_en")[0].as_py() == "Sahih al-Bukhari"

    def test_narrator_mentions_extracted(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        lk_dir = raw_dir / "lk"
        lk_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        _make_lk_csv(lk_dir / "albukhari.csv", _sample_rows())
        run(raw_dir, staging_dir)

        mentions_path = staging_dir / "narrator_mentions_lk.parquet"
        assert mentions_path.exists()
        table = pq.read_table(mentions_path)
        assert table.schema == NARRATOR_MENTION_SCHEMA
        assert table.num_rows > 0

    def test_no_csv_raises(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        lk_dir = raw_dir / "lk"
        lk_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        import pytest

        with pytest.raises(FileNotFoundError):
            run(raw_dir, staging_dir)

    def test_unknown_csv_skipped(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        lk_dir = raw_dir / "lk"
        lk_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        # An unknown file should be skipped; also include a known one so run() doesn't fail
        _make_lk_csv(lk_dir / "albukhari.csv", _sample_rows())
        _make_lk_csv(lk_dir / "unknown_collection.csv", _sample_rows())

        run(raw_dir, staging_dir)
        # Only bukhari should be parsed — 3 rows, not 6
        table = pq.read_table(staging_dir / "hadiths_lk.parquet")
        assert table.num_rows == 3
