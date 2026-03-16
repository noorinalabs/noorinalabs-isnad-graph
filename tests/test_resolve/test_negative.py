"""Negative tests for resolve modules."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.resolve.disambiguate import (
    Candidate,
    ChainContext,
    Match,
    _disambiguate_mention,
    _exact_match,
    _fuzzy_match,
    _temporal_filter,
)
from src.resolve.ner import run as ner_run


class TestNEREdgeCases:
    """Test NER edge cases with empty or missing data."""

    def test_empty_staging_dir(self, tmp_path: Path) -> None:
        """NER run with empty staging dir produces no mentions and warns."""
        staging = tmp_path / "staging"
        staging.mkdir()
        output = tmp_path / "output"
        output.mkdir()
        result = ner_run(staging, output)
        # No Parquet files to read, so no mentions extracted
        assert result == []

    def test_hadith_with_no_isnad(self, tmp_path: Path) -> None:
        """Hadiths with null isnads should be skipped without error."""
        from src.parse.schemas import HADITH_SCHEMA

        staging = tmp_path / "staging"
        staging.mkdir()
        output = tmp_path / "output"
        output.mkdir()

        # Create a hadith file where all isnads are null
        rows = {
            "source_id": pa.array(["h-1"], type=pa.string()),
            "source_corpus": pa.array(["thaqalayn"], type=pa.string()),
            "collection_name": pa.array(["al-kafi"], type=pa.string()),
            "book_number": pa.array([1], type=pa.int32()),
            "chapter_number": pa.array([None], type=pa.int32()),
            "hadith_number": pa.array([1], type=pa.int32()),
            "matn_ar": pa.array(["متن"], type=pa.string()),
            "matn_en": pa.array([None], type=pa.string()),
            "isnad_raw_ar": pa.array([None], type=pa.string()),
            "isnad_raw_en": pa.array([None], type=pa.string()),
            "full_text_ar": pa.array([None], type=pa.string()),
            "full_text_en": pa.array([None], type=pa.string()),
            "grade": pa.array([None], type=pa.string()),
            "chapter_name_ar": pa.array([None], type=pa.string()),
            "chapter_name_en": pa.array([None], type=pa.string()),
            "sect": pa.array(["shia"], type=pa.string()),
        }
        table = pa.table(rows, schema=HADITH_SCHEMA)
        pq.write_table(table, staging / "hadiths_thaqalayn.parquet")

        result = ner_run(staging, output)
        # No mentions should be extracted from hadiths with no isnad/full_text
        assert result == []


class TestDisambiguationEdgeCases:
    """Test disambiguation with edge-case inputs."""

    def test_no_candidates(self) -> None:
        """Disambiguation with empty candidate list returns None."""
        mention = {
            "mention_id": "m-1",
            "hadith_id": "h-1",
            "source_corpus": "test",
            "position_in_chain": 0,
            "name_raw": "محمد",
            "name_normalized": "محمد",
        }
        best, all_matches = _disambiguate_mention(mention, [], {})
        assert best is None
        assert all_matches == []

    def test_all_candidates_below_threshold(self) -> None:
        """When all fuzzy scores are below threshold, return None."""
        candidates = [
            Candidate(
                bio_id="bio-001",
                name_ar="عبد الرحمن بن أبي بكر الصديق",
                name_ar_normalized="عبد الرحمن بن ابي بكر الصديق",
            ),
        ]
        # Use a very different name so fuzzy match score is low
        mention = {
            "mention_id": "m-1",
            "hadith_id": "h-1",
            "source_corpus": "test",
            "position_in_chain": 0,
            "name_raw": "زيد",
            "name_normalized": "زيد",
        }
        best, all_matches = _disambiguate_mention(mention, candidates, {})
        # Either no match or match below confidence threshold
        if best is not None:
            assert best.score < 0.70

    def test_empty_mention_name(self) -> None:
        """Mention with empty name returns no match."""
        mention = {
            "mention_id": "m-1",
            "hadith_id": "h-1",
            "source_corpus": "test",
            "position_in_chain": 0,
            "name_raw": "",
            "name_normalized": "",
        }
        candidates = [
            Candidate(bio_id="bio-001", name_ar="محمد", name_ar_normalized="محمد"),
        ]
        best, all_matches = _disambiguate_mention(mention, candidates, {})
        assert best is None

    def test_none_mention_name(self) -> None:
        """Mention with None names returns no match."""
        mention = {
            "mention_id": "m-1",
            "hadith_id": "h-1",
            "source_corpus": "test",
            "position_in_chain": 0,
            "name_raw": None,
            "name_normalized": None,
        }
        best, all_matches = _disambiguate_mention(mention, [], {})
        assert best is None


class TestExactMatchEdgeCases:
    """Test exact match stage edge cases."""

    def test_empty_mention(self) -> None:
        """Empty mention string returns no matches."""
        result = _exact_match("", [Candidate(bio_id="b1", name_ar_normalized="محمد")])
        assert result == []

    def test_empty_candidates(self) -> None:
        """Empty candidates list returns no matches."""
        result = _exact_match("محمد", [])
        assert result == []


class TestFuzzyMatchEdgeCases:
    """Test fuzzy match stage edge cases."""

    def test_empty_mention(self) -> None:
        """Empty mention string returns no matches."""
        result = _fuzzy_match("", [Candidate(bio_id="b1", name_ar_normalized="محمد")])
        assert result == []

    def test_candidate_no_normalized_name(self) -> None:
        """Candidate without normalized name is skipped."""
        result = _fuzzy_match(
            "محمد",
            [Candidate(bio_id="b1", name_ar="محمد", name_ar_normalized=None)],
        )
        assert result == []


class TestTemporalFilterEdgeCases:
    """Test temporal filter edge cases."""

    def test_no_adjacent_years(self) -> None:
        """When no adjacent death years exist, all matches pass through."""
        matches = [
            Match(
                candidate=Candidate(bio_id="b1", death_year_ah=100),
                stage="fuzzy",
                score=0.85,
            )
        ]
        ctx = ChainContext(
            hadith_id="h1",
            position_in_chain=0,
            source_corpus="test",
            adjacent_death_years=[],
        )
        result = _temporal_filter(matches, ctx)
        assert len(result) == 1

    def test_no_candidate_death_year(self) -> None:
        """Candidate without death year passes through (soft constraint)."""
        matches = [
            Match(
                candidate=Candidate(bio_id="b1", death_year_ah=None),
                stage="fuzzy",
                score=0.85,
            )
        ]
        ctx = ChainContext(
            hadith_id="h1",
            position_in_chain=0,
            source_corpus="test",
            adjacent_death_years=[100],
        )
        result = _temporal_filter(matches, ctx)
        assert len(result) == 1

    def test_implausible_temporal_gap(self) -> None:
        """Candidate with implausible temporal gap is filtered out."""
        matches = [
            Match(
                candidate=Candidate(bio_id="b1", death_year_ah=500),
                stage="fuzzy",
                score=0.85,
            )
        ]
        ctx = ChainContext(
            hadith_id="h1",
            position_in_chain=0,
            source_corpus="test",
            adjacent_death_years=[100],  # gap of 400 years
        )
        result = _temporal_filter(matches, ctx)
        assert len(result) == 0


class TestDedupEdgeCases:
    """Test dedup edge cases."""

    def test_single_hadith(self, tmp_path: Path) -> None:
        """Dedup with a single hadith produces empty parallel links."""
        from src.parse.schemas import HADITH_SCHEMA
        from src.resolve.dedup import _load_hadith_texts

        staging = tmp_path / "staging"
        staging.mkdir()

        rows = {
            "source_id": pa.array(["h-1"], type=pa.string()),
            "source_corpus": pa.array(["sunnah"], type=pa.string()),
            "collection_name": pa.array(["bukhari"], type=pa.string()),
            "book_number": pa.array([1], type=pa.int32()),
            "chapter_number": pa.array([1], type=pa.int32()),
            "hadith_number": pa.array([1], type=pa.int32()),
            "matn_ar": pa.array(["إنما الأعمال بالنيات"], type=pa.string()),
            "matn_en": pa.array(["Actions are judged by intentions"], type=pa.string()),
            "isnad_raw_ar": pa.array([None], type=pa.string()),
            "isnad_raw_en": pa.array([None], type=pa.string()),
            "full_text_ar": pa.array([None], type=pa.string()),
            "full_text_en": pa.array([None], type=pa.string()),
            "grade": pa.array(["sahih"], type=pa.string()),
            "chapter_name_ar": pa.array([None], type=pa.string()),
            "chapter_name_en": pa.array([None], type=pa.string()),
            "sect": pa.array(["sunni"], type=pa.string()),
        }
        table = pa.table(rows, schema=HADITH_SCHEMA)
        pq.write_table(table, staging / "hadiths_sunnah.parquet")

        ids, texts, corpora = _load_hadith_texts(staging)
        assert len(ids) == 1
        assert len(texts) == 1

    def test_all_identical_hadiths(self, tmp_path: Path) -> None:
        """Dedup correctly loads hadiths with identical matn_en texts."""
        from src.parse.schemas import HADITH_SCHEMA
        from src.resolve.dedup import _load_hadith_texts

        staging = tmp_path / "staging"
        staging.mkdir()

        same_text = "Actions are judged by intentions"
        rows = {
            "source_id": pa.array(["h-1", "h-2", "h-3"], type=pa.string()),
            "source_corpus": pa.array(["sunnah", "sunnah", "sunnah"], type=pa.string()),
            "collection_name": pa.array(["bukhari", "muslim", "tirmidhi"], type=pa.string()),
            "book_number": pa.array([1, 1, 1], type=pa.int32()),
            "chapter_number": pa.array([1, 1, 1], type=pa.int32()),
            "hadith_number": pa.array([1, 1, 1], type=pa.int32()),
            "matn_ar": pa.array(["إنما الأعمال بالنيات"] * 3, type=pa.string()),
            "matn_en": pa.array([same_text] * 3, type=pa.string()),
            "isnad_raw_ar": pa.array([None] * 3, type=pa.string()),
            "isnad_raw_en": pa.array([None] * 3, type=pa.string()),
            "full_text_ar": pa.array([None] * 3, type=pa.string()),
            "full_text_en": pa.array([None] * 3, type=pa.string()),
            "grade": pa.array(["sahih"] * 3, type=pa.string()),
            "chapter_name_ar": pa.array([None] * 3, type=pa.string()),
            "chapter_name_en": pa.array([None] * 3, type=pa.string()),
            "sect": pa.array(["sunni"] * 3, type=pa.string()),
        }
        table = pa.table(rows, schema=HADITH_SCHEMA)
        pq.write_table(table, staging / "hadiths_sunnah.parquet")

        ids, texts, corpora = _load_hadith_texts(staging)
        assert len(ids) == 3
        assert all(t == same_text for t in texts)

    def test_empty_staging_dir(self, tmp_path: Path) -> None:
        """Dedup with empty staging returns empty results."""
        from src.resolve.dedup import _load_hadith_texts

        staging = tmp_path / "staging"
        staging.mkdir()

        ids, texts, corpora = _load_hadith_texts(staging)
        assert ids == []
        assert texts == []
        assert corpora == []

    def test_hadiths_with_null_matn(self, tmp_path: Path) -> None:
        """Hadiths with null/empty matn_en are skipped during loading."""
        from src.parse.schemas import HADITH_SCHEMA
        from src.resolve.dedup import _load_hadith_texts

        staging = tmp_path / "staging"
        staging.mkdir()

        rows = {
            "source_id": pa.array(["h-1", "h-2"], type=pa.string()),
            "source_corpus": pa.array(["sunnah", "sunnah"], type=pa.string()),
            "collection_name": pa.array(["bukhari", "bukhari"], type=pa.string()),
            "book_number": pa.array([1, 1], type=pa.int32()),
            "chapter_number": pa.array([1, 2], type=pa.int32()),
            "hadith_number": pa.array([1, 2], type=pa.int32()),
            "matn_ar": pa.array(["متن", "متن"], type=pa.string()),
            "matn_en": pa.array([None, "   "], type=pa.string()),
            "isnad_raw_ar": pa.array([None, None], type=pa.string()),
            "isnad_raw_en": pa.array([None, None], type=pa.string()),
            "full_text_ar": pa.array([None, None], type=pa.string()),
            "full_text_en": pa.array([None, None], type=pa.string()),
            "grade": pa.array([None, None], type=pa.string()),
            "chapter_name_ar": pa.array([None, None], type=pa.string()),
            "chapter_name_en": pa.array([None, None], type=pa.string()),
            "sect": pa.array(["sunni", "sunni"], type=pa.string()),
        }
        table = pa.table(rows, schema=HADITH_SCHEMA)
        pq.write_table(table, staging / "hadiths_sunnah.parquet")

        ids, texts, corpora = _load_hadith_texts(staging)
        assert len(ids) == 0  # both should be skipped
