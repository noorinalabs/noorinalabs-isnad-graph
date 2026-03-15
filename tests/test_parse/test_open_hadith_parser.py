"""End-to-end tests for the Open Hadith parser."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from src.parse.open_hadith import run
from src.parse.schemas import HADITH_SCHEMA


def _make_open_hadith_csv(raw_dir: Path) -> None:
    """Create minimal Open Hadith diacritics CSV test data."""
    oh_dir = raw_dir / "open_hadith"
    oh_dir.mkdir(parents=True)

    header = "hadith_number,text"
    rows = [
        "1,إنما الأعمال بالنيات",
        "2,لا ضرر ولا ضرار",
        "3,من حسن إسلام المرء تركه ما لا يعنيه",
    ]
    csv_path = oh_dir / "bukhari_tashkeel.csv"
    csv_path.write_text("\n".join([header, *rows]), encoding="utf-8")


class TestOpenHadithParser:
    def test_produces_parquet_file(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_open_hadith_csv(raw_dir)

        out_path = run(raw_dir, staging_dir)

        assert out_path.exists()
        assert "hadiths_open_hadith.parquet" in out_path.name

    def test_hadith_schema_conforms(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_open_hadith_csv(raw_dir)

        out_path = run(raw_dir, staging_dir)

        table = pq.read_table(out_path)
        assert table.schema == HADITH_SCHEMA
        assert table.num_rows == 3

    def test_source_corpus_field(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_open_hadith_csv(raw_dir)

        out_path = run(raw_dir, staging_dir)

        table = pq.read_table(out_path)
        corpora = table.column("source_corpus").to_pylist()
        assert all(c == "open_hadith" for c in corpora)

    def test_no_source_dir_raises(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        import pytest

        with pytest.raises(FileNotFoundError):
            run(raw_dir, staging_dir)
