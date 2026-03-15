"""Tests for src.resolve.ner — narrator NER extraction pipeline."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.parse.schemas import NARRATOR_MENTION_SCHEMA
from src.resolve.ner import _extract_from_hadiths, _load_phase1_mentions, run
from src.resolve.schemas import NARRATOR_MENTIONS_RESOLVED_SCHEMA
from tests.test_resolve.conftest import write_hadiths


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_narrator_mentions_parquet(path: Path, rows: list[dict]) -> Path:
    """Write a narrator_mentions Parquet with NARRATOR_MENTION_SCHEMA."""
    arrays = {
        "mention_id": pa.array([r["mention_id"] for r in rows], type=pa.string()),
        "source_hadith_id": pa.array(
            [r["source_hadith_id"] for r in rows], type=pa.string()
        ),
        "source_corpus": pa.array([r["source_corpus"] for r in rows], type=pa.string()),
        "position_in_chain": pa.array(
            [r["position_in_chain"] for r in rows], type=pa.int32()
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
    pq.write_table(table, path)
    return path


# ---------------------------------------------------------------------------
# Tests: Phase 1 mention loading
# ---------------------------------------------------------------------------
class TestLoadPhase1Mentions:
    def test_loads_existing_mentions(self, tmp_path: Path) -> None:
        mentions = [
            {
                "mention_id": "m-1",
                "source_hadith_id": "h-1",
                "source_corpus": "sanadset",
                "position_in_chain": 0,
                "name_ar": "\u0623\u0628\u0648 \u0647\u0631\u064a\u0631\u0629",
                "name_en": "Abu Hurayra",
                "name_ar_normalized": "\u0627\u0628\u0648 \u0647\u0631\u064a\u0631\u0647",
                "transmission_method": "haddathana",
            },
        ]
        _write_narrator_mentions_parquet(
            tmp_path / "narrator_mentions_sanadset.parquet", mentions
        )
        rows = _load_phase1_mentions(
            tmp_path, "sanadset", "narrator_mentions_sanadset.parquet"
        )
        assert len(rows) == 1
        assert rows[0]["source_corpus"] == "sanadset"
        assert rows[0]["name_raw"] is not None
        assert rows[0]["mention_id"] is not None

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        rows = _load_phase1_mentions(tmp_path, "sanadset", "missing.parquet")
        assert rows == []

    def test_prefers_arabic_name(self, tmp_path: Path) -> None:
        mentions = [
            {
                "mention_id": "m-2",
                "source_hadith_id": "h-2",
                "source_corpus": "lk",
                "position_in_chain": 1,
                "name_ar": "\u0639\u0644\u064a",
                "name_en": "Ali",
                "name_ar_normalized": "\u0639\u0644\u064a",
                "transmission_method": None,
            },
        ]
        _write_narrator_mentions_parquet(
            tmp_path / "narrator_mentions_lk.parquet", mentions
        )
        rows = _load_phase1_mentions(tmp_path, "lk", "narrator_mentions_lk.parquet")
        assert rows[0]["name_raw"] == "\u0639\u0644\u064a"

    def test_falls_back_to_english_name(self, tmp_path: Path) -> None:
        mentions = [
            {
                "mention_id": "m-3",
                "source_hadith_id": "h-3",
                "source_corpus": "lk",
                "position_in_chain": 0,
                "name_ar": None,
                "name_en": "Malik",
                "name_ar_normalized": None,
                "transmission_method": None,
            },
        ]
        _write_narrator_mentions_parquet(
            tmp_path / "narrator_mentions_lk.parquet", mentions
        )
        rows = _load_phase1_mentions(tmp_path, "lk", "narrator_mentions_lk.parquet")
        assert rows[0]["name_raw"] == "Malik"
        assert rows[0]["name_normalized"] == "Malik"


# ---------------------------------------------------------------------------
# Tests: Arabic extraction
# ---------------------------------------------------------------------------
class TestArabicExtraction:
    def test_extracts_from_arabic_isnad(self, tmp_path: Path) -> None:
        hadiths = [
            {
                "source_id": "th-1",
                "source_corpus": "thaqalayn",
                "collection_name": "al-kafi",
                "isnad_raw_ar": (
                    "\u062d\u062f\u062b\u0646\u0627 \u0645\u062d\u0645\u062f"
                    " \u0639\u0646 \u0639\u0644\u064a"
                ),
                "isnad_raw_en": None,
                "full_text_ar": None,
                "full_text_en": None,
                "matn_ar": "text",
                "matn_en": None,
                "grade": None,
                "sect": "shia",
                "book_number": 1,
                "chapter_number": 1,
                "hadith_number": 1,
                "chapter_name_ar": None,
                "chapter_name_en": None,
            },
        ]
        write_hadiths(tmp_path / "hadiths_thaqalayn.parquet", hadiths)
        rows = _extract_from_hadiths(tmp_path, "thaqalayn", "ar")
        assert len(rows) > 0
        assert all(r["source_corpus"] == "thaqalayn" for r in rows)

    def test_falls_back_to_full_text(self, tmp_path: Path) -> None:
        hadiths = [
            {
                "source_id": "th-2",
                "source_corpus": "thaqalayn",
                "collection_name": "al-kafi",
                "isnad_raw_ar": None,
                "isnad_raw_en": None,
                "full_text_ar": "\u062d\u062f\u062b\u0646\u0627 \u0623\u0646\u0633",
                "full_text_en": None,
                "matn_ar": None,
                "matn_en": None,
                "grade": None,
                "sect": "shia",
                "book_number": 1,
                "chapter_number": 1,
                "hadith_number": 1,
                "chapter_name_ar": None,
                "chapter_name_en": None,
            },
        ]
        write_hadiths(tmp_path / "hadiths_thaqalayn.parquet", hadiths)
        rows = _extract_from_hadiths(tmp_path, "thaqalayn", "ar")
        assert len(rows) > 0


# ---------------------------------------------------------------------------
# Tests: English extraction
# ---------------------------------------------------------------------------
class TestEnglishExtraction:
    def test_extracts_from_english_isnad(self, tmp_path: Path) -> None:
        hadiths = [
            {
                "source_id": "fw-1",
                "source_corpus": "fawaz",
                "collection_name": "fawaz-collection",
                "isnad_raw_ar": None,
                "isnad_raw_en": "Narrated Abu Hurayra from the Prophet",
                "full_text_ar": None,
                "full_text_en": None,
                "matn_ar": None,
                "matn_en": "The Prophet said...",
                "grade": None,
                "sect": "sunni",
                "book_number": 1,
                "chapter_number": 1,
                "hadith_number": 1,
                "chapter_name_ar": None,
                "chapter_name_en": None,
            },
        ]
        write_hadiths(tmp_path / "hadiths_fawaz.parquet", hadiths)
        rows = _extract_from_hadiths(tmp_path, "fawaz", "en")
        assert len(rows) > 0
        assert all(r["source_corpus"] == "fawaz" for r in rows)

    def test_no_hadith_files_returns_empty(self, tmp_path: Path) -> None:
        rows = _extract_from_hadiths(tmp_path, "fawaz", "en")
        assert rows == []


# ---------------------------------------------------------------------------
# Tests: Null/empty isnad handling
# ---------------------------------------------------------------------------
class TestNullHandling:
    def test_null_isnad_and_full_text_skips_row(self, tmp_path: Path) -> None:
        hadiths = [
            {
                "source_id": "fw-null",
                "source_corpus": "fawaz",
                "collection_name": "fawaz-collection",
                "isnad_raw_ar": None,
                "isnad_raw_en": None,
                "full_text_ar": None,
                "full_text_en": None,
                "matn_ar": None,
                "matn_en": None,
                "grade": None,
                "sect": "sunni",
                "book_number": None,
                "chapter_number": None,
                "hadith_number": None,
                "chapter_name_ar": None,
                "chapter_name_en": None,
            },
        ]
        write_hadiths(tmp_path / "hadiths_fawaz.parquet", hadiths)
        rows = _extract_from_hadiths(tmp_path, "fawaz", "en")
        assert rows == []

    def test_empty_string_isnad_skips_row(self, tmp_path: Path) -> None:
        hadiths = [
            {
                "source_id": "fw-empty",
                "source_corpus": "fawaz",
                "collection_name": "fawaz-collection",
                "isnad_raw_ar": None,
                "isnad_raw_en": "",
                "full_text_ar": None,
                "full_text_en": "",
                "matn_ar": None,
                "matn_en": None,
                "grade": None,
                "sect": "sunni",
                "book_number": None,
                "chapter_number": None,
                "hadith_number": None,
                "chapter_name_ar": None,
                "chapter_name_en": None,
            },
        ]
        write_hadiths(tmp_path / "hadiths_fawaz.parquet", hadiths)
        rows = _extract_from_hadiths(tmp_path, "fawaz", "en")
        assert rows == []


# ---------------------------------------------------------------------------
# Tests: Output schema conformance
# ---------------------------------------------------------------------------
class TestOutputSchema:
    def test_output_matches_resolved_schema(self, tmp_path: Path) -> None:
        """Full run should produce a Parquet matching NARRATOR_MENTIONS_RESOLVED_SCHEMA."""
        staging = tmp_path / "staging"
        staging.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        # Create a minimal English source.
        hadiths = [
            {
                "source_id": "fw-schema",
                "source_corpus": "fawaz",
                "collection_name": "fawaz-collection",
                "isnad_raw_ar": None,
                "isnad_raw_en": "Narrated Abu Bakr from Umar",
                "full_text_ar": None,
                "full_text_en": None,
                "matn_ar": None,
                "matn_en": "Text",
                "grade": None,
                "sect": "sunni",
                "book_number": 1,
                "chapter_number": 1,
                "hadith_number": 1,
                "chapter_name_ar": None,
                "chapter_name_en": None,
            },
        ]
        write_hadiths(staging / "hadiths_fawaz.parquet", hadiths)

        paths = run(staging, output)
        assert len(paths) >= 1

        resolved_path = output / "narrator_mentions_resolved.parquet"
        assert resolved_path.exists()

        table = pq.read_table(resolved_path)
        assert table.schema.equals(NARRATOR_MENTIONS_RESOLVED_SCHEMA)

    def test_run_with_no_data_produces_no_output(self, tmp_path: Path) -> None:
        staging = tmp_path / "staging"
        staging.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        paths = run(staging, output)
        assert paths == []
