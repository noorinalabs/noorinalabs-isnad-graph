"""Real data flow integration tests.

These tests validate that the pipeline works end-to-end with real
(sampled) data. They require Docker containers and are marked with
@pytest.mark.integration.

Run: pytest tests/integration/test_real_data_flow.py -v -m integration
"""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.parse import lk_corpus, sanadset
from src.parse.schemas import HADITH_SCHEMA, NARRATOR_MENTION_SCHEMA
from src.parse.validate import validate_staging


def _create_sample_lk_csv(directory: Path) -> Path:
    """Create a minimal LK-format CSV for testing."""
    lk_dir = directory / "lk"
    lk_dir.mkdir(parents=True, exist_ok=True)
    csv_path = lk_dir / "albukhari.csv"
    csv_path.write_text(
        "Chapter_Number,Chapter_English,Chapter_Arabic,Section_Number,"
        "Section_English,Section_Arabic,Hadith_number,English_Hadith,"
        "English_Isnad,English_Matn,Arabic_Hadith,Arabic_Isnad,Arabic_Matn,"
        "Arabic_Comment,English_Grade,Arabic_Grade\n"
        "1,Revelation,كتاب بدء الوحي,1,Section 1,الباب الأول,1,"
        '"Narrated by Ibn Umar: The Prophet said...",'
        '"Narrated by Ibn Umar",'
        '"The Prophet said...",'
        '"حدثنا ابن عمر قال: قال رسول الله...",'
        '"حدثنا ابن عمر",'
        '"قال رسول الله...",'
        ",Sahih,صحيح\n"
        "1,Revelation,كتاب بدء الوحي,1,Section 1,الباب الأول,2,"
        '"Narrated by Aisha: The Prophet said...",'
        '"Narrated by Aisha",'
        '"The Prophet said...",'
        '"حدثنا عائشة قالت: قال رسول الله...",'
        '"حدثنا عائشة",'
        '"قال رسول الله...",'
        ",Sahih,صحيح\n"
        "1,Revelation,كتاب بدء الوحي,1,Section 1,الباب الأول,3,"
        '"Narrated by Abu Hurairah: The Prophet said...",'
        '"Narrated by Abu Hurairah",'
        '"The Prophet said...",'
        '"حدثنا أبو هريرة قال: قال رسول الله...",'
        '"حدثنا أبو هريرة",'
        '"قال رسول الله...",'
        ",Sahih,صحيح\n",
        encoding="utf-8",
    )
    return csv_path


def _create_sample_sanadset_csv(directory: Path) -> Path:
    """Create a minimal Sanadset-format CSV for testing."""
    sanadset_dir = directory / "sanadset"
    sanadset_dir.mkdir(parents=True, exist_ok=True)
    csv_path = sanadset_dir / "sample_collection.csv"
    csv_path.write_text(
        "hadith_id,book_id,hadith,grade\n"
        '1,1,"<SANAD>حدثنا <NAR>عبد الله بن يوسف</NAR> عن <NAR>مالك</NAR></SANAD>'
        '<MATN>أن رسول الله صلى الله عليه وسلم قال</MATN>",صحيح\n'
        '2,1,"<SANAD>حدثنا <NAR>أحمد بن حنبل</NAR> عن <NAR>سفيان</NAR></SANAD>'
        '<MATN>قال رسول الله صلى الله عليه وسلم</MATN>",حسن\n'
        '3,1,"<SANAD>No SANAD</SANAD><MATN>قال النبي</MATN>",ضعيف\n',
        encoding="utf-8",
    )
    return csv_path


@pytest.mark.integration
class TestRealDataFlow:
    """Integration tests for real data flow through the pipeline."""

    def test_parse_sample_lk_data(self, tmp_path: Path) -> None:
        """Parse a sample of LK corpus data and validate output."""
        _create_sample_lk_csv(tmp_path)
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        output_paths = lk_corpus.run(tmp_path, staging_dir)

        assert len(output_paths) >= 1
        hadith_path = staging_dir / "hadiths_lk.parquet"
        assert hadith_path.exists()

        table = pq.read_table(hadith_path)
        assert table.num_rows == 3
        assert set(HADITH_SCHEMA.names).issubset(set(table.column_names))

        # Verify content
        rows = table.to_pylist()
        assert all(r["source_corpus"] == "lk" for r in rows)
        assert all(r["collection_name"] == "bukhari" for r in rows)
        assert all(r["sect"] == "sunni" for r in rows)

    def test_parse_sample_sanadset_data(self, tmp_path: Path) -> None:
        """Parse sample Sanadset data with real NAR tags."""
        _create_sample_sanadset_csv(tmp_path)
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        sanadset_dir = tmp_path / "sanadset"
        outputs = sanadset.parse_sanadset(raw_dir=sanadset_dir, staging_dir=staging_dir)

        assert "hadiths" in outputs
        hadith_path = outputs["hadiths"]
        assert hadith_path.exists()

        table = pq.read_table(hadith_path)
        assert table.num_rows == 3

        # Check narrator mentions were extracted from NAR tags
        if "narrator_mentions" in outputs:
            mentions_table = pq.read_table(outputs["narrator_mentions"])
            assert mentions_table.num_rows >= 2
            assert set(NARRATOR_MENTION_SCHEMA.names).issubset(set(mentions_table.column_names))

    def test_staging_validation_on_parsed_data(self, tmp_path: Path) -> None:
        """Run validate_staging on parsed output."""
        _create_sample_lk_csv(tmp_path)
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        lk_corpus.run(tmp_path, staging_dir)
        summary = validate_staging(staging_dir)

        assert summary["total_files"] >= 1
        assert summary["total_rows"] >= 3

        for file_info in summary["files"]:
            assert file_info["schema_issues"] == [], (
                f"Schema issues in {file_info['file']}: {file_info['schema_issues']}"
            )

    def test_full_pipeline_sample(self, tmp_path: Path, neo4j_client) -> None:
        """End-to-end: parse -> load nodes -> load edges -> validate graph."""
        from src.graph.load_edges import load_all_edges
        from src.graph.load_nodes import load_all_nodes

        _create_sample_lk_csv(tmp_path)
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()
        curated_dir = tmp_path / "curated"
        curated_dir.mkdir()

        # Parse
        lk_corpus.run(tmp_path, staging_dir)

        # Load nodes (non-strict: skip missing files like narrators_canonical)
        node_results = load_all_nodes(neo4j_client, staging_dir, curated_dir, strict=False)
        hadith_result = next(r for r in node_results if r.node_type == "Hadith")
        assert hadith_result.created == 3

        collection_result = next(r for r in node_results if r.node_type == "Collection")
        assert collection_result.created == 1

        # Load edges (non-strict)
        edge_results = load_all_edges(neo4j_client, staging_dir, curated_dir, strict=False)
        appears_in = next(r for r in edge_results if r.edge_type == "APPEARS_IN")
        # All 3 hadiths should link to the bukhari collection
        assert appears_in.created == 3

        # Validate: check nodes exist in graph
        hadith_count = neo4j_client.execute_read("MATCH (h:Hadith) RETURN count(h) AS cnt")
        assert hadith_count[0]["cnt"] == 3

        coll_count = neo4j_client.execute_read("MATCH (c:Collection) RETURN count(c) AS cnt")
        assert coll_count[0]["cnt"] == 1
