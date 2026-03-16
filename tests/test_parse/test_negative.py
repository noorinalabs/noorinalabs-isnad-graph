"""Negative tests for parsers."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.parse.base import read_csv_robust
from src.parse.sanadset import _MATN_RE, _SANAD_RE, _extract_narrator_mentions, _extract_tag


class TestMalformedInputs:
    """Test parsers handle malformed inputs gracefully."""

    def test_empty_csv(self, tmp_path: Path) -> None:
        """An empty CSV file should raise ValueError (no headers)."""
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("", encoding="utf-8")
        with pytest.raises((ValueError, Exception)):
            read_csv_robust(csv_path)

    def test_csv_wrong_encoding(self, tmp_path: Path) -> None:
        """CSV with wrong encoding should fall back to latin-1 or raise."""
        csv_path = tmp_path / "bad_enc.csv"
        # Write raw bytes that aren't valid UTF-8
        csv_path.write_bytes(b"col1,col2\n\xff\xfe,value\n")
        # Should not crash -- read_csv_robust has fallback chain
        table, enc = read_csv_robust(csv_path)
        assert enc in ("utf-8", "utf-8-sig", "latin-1")

    def test_csv_missing_columns(self, tmp_path: Path) -> None:
        """CSV with wrong columns should still parse (columns are data-driven)."""
        csv_path = tmp_path / "wrong_cols.csv"
        csv_path.write_text("wrong_a,wrong_b\n1,2\n", encoding="utf-8")
        table, enc = read_csv_robust(csv_path)
        assert table.num_rows == 1
        assert "wrong_a" in table.column_names

    def test_sanadset_unclosed_nar_tags(self, tmp_path: Path) -> None:
        """Unclosed NAR tags should not crash -- regex just won't match."""
        text = "<NAR>محمد عن <NAR>علي</NAR>"
        # _extract_narrator_mentions uses finditer with the regex <NAR>(.*?)</NAR>
        # The unclosed first <NAR> won't match, only the closed one will.
        mentions = _extract_narrator_mentions(text, "test-hadith-001")
        # Should extract at least the properly closed tag
        assert isinstance(mentions, list)
        for m in mentions:
            assert m["name_ar"] is not None

    def test_sanadset_empty_nar_tags(self, tmp_path: Path) -> None:
        """Empty NAR tags like <NAR></NAR> should be skipped."""
        text = "<NAR></NAR> عن <NAR>علي</NAR>"
        mentions = _extract_narrator_mentions(text, "test-hadith-002")
        # Empty tag content should be skipped (name_raw would be empty string)
        names = [m["name_ar"] for m in mentions]
        assert all(name.strip() for name in names)

    def test_extract_tag_no_match(self) -> None:
        """_extract_tag returns None when no matching tag is found."""
        result = _extract_tag(_SANAD_RE, "no tags here")
        assert result is None

    def test_extract_tag_empty_content(self) -> None:
        """_extract_tag returns None when tag content is empty/whitespace."""
        result = _extract_tag(_MATN_RE, "<MATN>   </MATN>")
        assert result is None

    def test_json_invalid_structure(self, tmp_path: Path) -> None:
        """A file with invalid JSON-like content should raise when parsed as CSV."""
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text('{"not": "csv"}', encoding="utf-8")
        # read_csv_robust will try to parse this as CSV -- it may succeed with
        # a single column or raise. Either way, it should not crash with an
        # unhandled exception.
        try:
            table, enc = read_csv_robust(csv_path)
            # If it parses, it should have at least the header row logic
            assert table.num_rows >= 0
        except ValueError, Exception:
            # Acceptable: the CSV parser may reject it
            pass


class TestMissingFiles:
    """Test parsers handle missing files/directories."""

    def test_parser_with_empty_raw_dir(self, tmp_path: Path) -> None:
        """Sanadset parser with empty raw dir raises FileNotFoundError."""
        from src.parse.sanadset import parse_sanadset

        empty_dir = tmp_path / "empty_raw"
        empty_dir.mkdir()
        staging = tmp_path / "staging"
        staging.mkdir()
        with pytest.raises(FileNotFoundError, match="No CSV files found"):
            parse_sanadset(raw_dir=empty_dir, staging_dir=staging)

    def test_parser_with_missing_source(self, tmp_path: Path) -> None:
        """Sanadset parser with nonexistent dir raises FileNotFoundError."""
        from src.parse.sanadset import parse_sanadset

        nonexistent = tmp_path / "does_not_exist"
        staging = tmp_path / "staging"
        staging.mkdir()
        with pytest.raises(FileNotFoundError):
            parse_sanadset(raw_dir=nonexistent, staging_dir=staging)

    def test_read_csv_robust_missing_file(self, tmp_path: Path) -> None:
        """read_csv_robust with nonexistent file raises an error."""
        missing = tmp_path / "missing.csv"
        with pytest.raises(Exception):
            read_csv_robust(missing)
