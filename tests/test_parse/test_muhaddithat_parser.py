"""End-to-end tests for the Muhaddithat parser."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from src.parse.muhaddithat import run
from src.parse.schemas import NARRATOR_BIO_SCHEMA, NETWORK_EDGE_SCHEMA


def _make_muhaddithat_data(raw_dir: Path) -> None:
    """Create minimal Muhaddithat CSV test data (narrators + hadiths)."""
    muh_dir = raw_dir / "muhaddithat"
    muh_dir.mkdir(parents=True)

    # Narrators CSV
    narrators_csv = "id,name,gender,bio\n"
    narrators_csv += "N1,فاطمة بنت الحسين,female,عالمة\n"
    narrators_csv += "N2,عائشة بنت أبي بكر,female,أم المؤمنين\n"
    narrators_csv += "N3,أم سلمة,female,أم المؤمنين\n"
    (muh_dir / "narrators.csv").write_text(narrators_csv, encoding="utf-8")

    # Hadiths CSV with narrator ID chains
    hadiths_csv = "id,narrator_ids,text\n"
    hadiths_csv += '1,"N1,N2",متن الحديث الأول\n'
    hadiths_csv += '2,"N2,N3",متن الحديث الثاني\n'
    hadiths_csv += '3,"N1,N2,N3",متن الحديث الثالث\n'
    (muh_dir / "hadiths.csv").write_text(hadiths_csv, encoding="utf-8")


class TestMuhaddithatParser:
    def test_produces_parquet_files(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_muhaddithat_data(raw_dir)

        bio_path, edge_path = run(raw_dir, staging_dir)

        assert bio_path.exists()
        assert edge_path.exists()

    def test_bio_schema_conforms(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_muhaddithat_data(raw_dir)

        bio_path, _ = run(raw_dir, staging_dir)

        table = pq.read_table(bio_path)
        assert table.schema == NARRATOR_BIO_SCHEMA
        assert table.num_rows == 3

    def test_edge_schema_conforms(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_muhaddithat_data(raw_dir)

        _, edge_path = run(raw_dir, staging_dir)

        table = pq.read_table(edge_path)
        assert table.schema == NETWORK_EDGE_SCHEMA
        assert table.num_rows > 0

    def test_edge_count(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        staging_dir = tmp_path / "staging"
        _make_muhaddithat_data(raw_dir)

        _, edge_path = run(raw_dir, staging_dir)

        table = pq.read_table(edge_path)
        # Hadith 1: N1->N2 (1 edge), Hadith 2: N2->N3 (1 edge),
        # Hadith 3: N1->N2, N2->N3 (2 edges) => 4 total
        assert table.num_rows == 4

    def test_variousnarrators_csv_found(self, tmp_path: Path) -> None:
        """Parser should find variousnarrators.csv as the narrator file."""
        raw_dir = tmp_path / "raw"
        muh_dir = raw_dir / "muhaddithat"
        muh_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        narrators_csv = "id,name,gender,bio\n"
        narrators_csv += "N1,فاطمة بنت الحسين,female,عالمة\n"
        narrators_csv += "N2,عائشة بنت أبي بكر,female,أم المؤمنين\n"
        (muh_dir / "variousnarrators.csv").write_text(narrators_csv, encoding="utf-8")

        hadiths_csv = "id,narrator_ids,text\n"
        hadiths_csv += '1,"N1,N2",متن الحديث\n'
        (muh_dir / "hadiths.csv").write_text(hadiths_csv, encoding="utf-8")

        bio_path, edge_path = run(raw_dir, staging_dir)
        assert bio_path.exists()
        table = pq.read_table(bio_path)
        assert table.num_rows == 2

    def test_no_source_dir_raises(self, tmp_path: Path) -> None:
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir(parents=True)
        staging_dir = tmp_path / "staging"

        import pytest

        with pytest.raises(FileNotFoundError):
            run(raw_dir, staging_dir)
