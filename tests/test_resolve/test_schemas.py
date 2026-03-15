"""Tests for src.resolve.schemas — Phase 2 resolve output schemas."""

from __future__ import annotations

import pyarrow as pa
import pytest

from src.resolve.schemas import (
    AMBIGUOUS_NARRATORS_SCHEMA,
    NARRATOR_MENTIONS_RESOLVED_SCHEMA,
    NARRATORS_CANONICAL_SCHEMA,
    PARALLEL_LINKS_SCHEMA,
)

_ALL_SCHEMAS = [
    ("NARRATOR_MENTIONS_RESOLVED_SCHEMA", NARRATOR_MENTIONS_RESOLVED_SCHEMA),
    ("NARRATORS_CANONICAL_SCHEMA", NARRATORS_CANONICAL_SCHEMA),
    ("AMBIGUOUS_NARRATORS_SCHEMA", AMBIGUOUS_NARRATORS_SCHEMA),
    ("PARALLEL_LINKS_SCHEMA", PARALLEL_LINKS_SCHEMA),
]


class TestEmptyTables:
    @pytest.mark.parametrize("name,schema", _ALL_SCHEMAS, ids=[s[0] for s in _ALL_SCHEMAS])
    def test_empty_table_creation(self, name: str, schema: pa.Schema) -> None:
        table = schema.empty_table()
        assert table.num_rows == 0
        assert table.schema.equals(schema)


class TestSampleData:
    def test_narrator_mentions_resolved(self) -> None:
        data = {
            "mention_id": pa.array(["m-1"], type=pa.string()),
            "hadith_id": pa.array(["h-1"], type=pa.string()),
            "source_corpus": pa.array(["sunnah"], type=pa.string()),
            "position_in_chain": pa.array([0], type=pa.int32()),
            "name_raw": pa.array(["Abu Hurayra"], type=pa.string()),
            "name_normalized": pa.array(["abu hurayra"], type=pa.string()),
            "canonical_narrator_id": pa.array([None], type=pa.string()),
            "transmission_method": pa.array(["haddathana"], type=pa.string()),
            "confidence": pa.array([None], type=pa.float32()),
        }
        table = pa.table(data, schema=NARRATOR_MENTIONS_RESOLVED_SCHEMA)
        assert table.num_rows == 1
        assert table.schema.equals(NARRATOR_MENTIONS_RESOLVED_SCHEMA)

    def test_narrators_canonical(self) -> None:
        data = {
            "canonical_id": pa.array(["c-1"], type=pa.string()),
            "name_ar": pa.array(["\u0639\u0644\u064a"], type=pa.string()),
            "name_en": pa.array(["Ali"], type=pa.string()),
            "name_ar_normalized": pa.array(["\u0639\u0644\u064a"], type=pa.string()),
            "aliases": pa.array([["Ali ibn Abi Talib"]], type=pa.list_(pa.string())),
            "birth_year_ah": pa.array([None], type=pa.int32()),
            "death_year_ah": pa.array([40], type=pa.int32()),
            "generation": pa.array(["sahabi"], type=pa.string()),
            "gender": pa.array(["male"], type=pa.string()),
            "trustworthiness": pa.array(["thiqa"], type=pa.string()),
            "source_ids": pa.array([["bio-1"]], type=pa.list_(pa.string())),
            "external_id": pa.array([None], type=pa.string()),
            "mention_count": pa.array([5], type=pa.int32()),
        }
        table = pa.table(data, schema=NARRATORS_CANONICAL_SCHEMA)
        assert table.num_rows == 1

    def test_ambiguous_narrators(self) -> None:
        data = {
            "mention_id": pa.array(["m-1"], type=pa.string()),
            "mention_text": pa.array(["ambiguous name"], type=pa.string()),
            "source_corpus": pa.array(["sunnah"], type=pa.string()),
            "candidate_1_id": pa.array(["c-1"], type=pa.string()),
            "candidate_1_name": pa.array(["Name A"], type=pa.string()),
            "candidate_1_score": pa.array([0.65], type=pa.float32()),
            "candidate_1_stage": pa.array(["fuzzy"], type=pa.string()),
            "candidate_2_id": pa.array([None], type=pa.string()),
            "candidate_2_name": pa.array([None], type=pa.string()),
            "candidate_2_score": pa.array([None], type=pa.float32()),
            "candidate_2_stage": pa.array([None], type=pa.string()),
            "candidate_3_id": pa.array([None], type=pa.string()),
            "candidate_3_name": pa.array([None], type=pa.string()),
            "candidate_3_score": pa.array([None], type=pa.float32()),
            "candidate_3_stage": pa.array([None], type=pa.string()),
        }
        table = pa.table(data, schema=AMBIGUOUS_NARRATORS_SCHEMA)
        assert table.num_rows == 1

    def test_parallel_links(self) -> None:
        data = {
            "hadith_id_a": pa.array(["h-1"], type=pa.string()),
            "hadith_id_b": pa.array(["h-2"], type=pa.string()),
            "similarity_score": pa.array([0.92], type=pa.float32()),
            "variant_type": pa.array(["verbatim"], type=pa.string()),
            "cross_sect": pa.array([False], type=pa.bool_()),
        }
        table = pa.table(data, schema=PARALLEL_LINKS_SCHEMA)
        assert table.num_rows == 1
