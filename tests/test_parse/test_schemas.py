"""Tests for staging Parquet schemas."""

from __future__ import annotations

import pyarrow as pa

from src.parse.schemas import (
    COLLECTION_SCHEMA,
    HADITH_SCHEMA,
    NARRATOR_BIO_SCHEMA,
    NARRATOR_MENTION_SCHEMA,
    NETWORK_EDGE_SCHEMA,
)


class TestEmptyTables:
    """Each schema should be able to create an empty table."""

    def test_hadith_schema_empty(self) -> None:
        table = pa.table({f.name: [] for f in HADITH_SCHEMA}, schema=HADITH_SCHEMA)
        assert table.num_rows == 0
        assert table.schema == HADITH_SCHEMA

    def test_narrator_mention_schema_empty(self) -> None:
        table = pa.table(
            {f.name: [] for f in NARRATOR_MENTION_SCHEMA}, schema=NARRATOR_MENTION_SCHEMA
        )
        assert table.num_rows == 0
        assert table.schema == NARRATOR_MENTION_SCHEMA

    def test_narrator_bio_schema_empty(self) -> None:
        table = pa.table({f.name: [] for f in NARRATOR_BIO_SCHEMA}, schema=NARRATOR_BIO_SCHEMA)
        assert table.num_rows == 0
        assert table.schema == NARRATOR_BIO_SCHEMA

    def test_collection_schema_empty(self) -> None:
        table = pa.table({f.name: [] for f in COLLECTION_SCHEMA}, schema=COLLECTION_SCHEMA)
        assert table.num_rows == 0
        assert table.schema == COLLECTION_SCHEMA

    def test_network_edge_schema_empty(self) -> None:
        table = pa.table({f.name: [] for f in NETWORK_EDGE_SCHEMA}, schema=NETWORK_EDGE_SCHEMA)
        assert table.num_rows == 0
        assert table.schema == NETWORK_EDGE_SCHEMA


class TestSampleData:
    """Each schema should accept sample data and cast correctly."""

    def test_hadith_schema_with_data(self) -> None:
        data = {
            "source_id": ["lk:bukhari:1:1"],
            "source_corpus": ["lk"],
            "collection_name": ["bukhari"],
            "book_number": [1],
            "chapter_number": [1],
            "hadith_number": [1],
            "matn_ar": ["إنما الأعمال بالنيات"],
            "matn_en": ["Actions are by intentions"],
            "isnad_raw_ar": ["حدثنا الحميدي"],
            "isnad_raw_en": ["Narrated Umar ibn al-Khattab"],
            "full_text_ar": [None],
            "full_text_en": [None],
            "grade": ["Sahih"],
            "chapter_name_ar": [None],
            "chapter_name_en": ["Revelation"],
            "sect": ["sunni"],
        }
        table = pa.table(data).cast(HADITH_SCHEMA)
        assert table.num_rows == 1
        assert table.column("source_id")[0].as_py() == "lk:bukhari:1:1"

    def test_narrator_mention_schema_with_data(self) -> None:
        data = {
            "mention_id": ["lk:bukhari:1:1:en:0"],
            "source_hadith_id": ["lk:bukhari:1:1"],
            "source_corpus": ["lk"],
            "position_in_chain": [0],
            "name_ar": [None],
            "name_en": ["Abu Hurayra"],
            "name_ar_normalized": [None],
            "transmission_method": [None],
        }
        table = pa.table(data).cast(NARRATOR_MENTION_SCHEMA)
        assert table.num_rows == 1

    def test_collection_schema_with_data(self) -> None:
        data = {
            "collection_id": ["lk:bukhari"],
            "name_ar": [None],
            "name_en": ["Sahih al-Bukhari"],
            "compiler_name": ["Muhammad ibn Ismail al-Bukhari"],
            "compilation_year_ah": [256],
            "sect": ["sunni"],
            "total_hadiths": [7563],
            "source_corpus": ["lk"],
        }
        table = pa.table(data).cast(COLLECTION_SCHEMA)
        assert table.num_rows == 1

    def test_network_edge_schema_with_data(self) -> None:
        data = {
            "from_narrator_name": ["Malik"],
            "to_narrator_name": ["Nafi"],
            "hadith_id": ["lk:bukhari:1:1"],
            "source": ["lk"],
            "from_external_id": [None],
            "to_external_id": [None],
        }
        table = pa.table(data).cast(NETWORK_EDGE_SCHEMA)
        assert table.num_rows == 1

    def test_narrator_bio_schema_with_data(self) -> None:
        data = {
            "bio_id": ["kaggle:narrators:1"],
            "source": ["kaggle_narrators"],
            "name_ar": ["أبو هريرة"],
            "name_en": ["Abu Hurayra"],
            "name_ar_normalized": ["ابو هريره"],
            "name_en_normalized": [None],
            "kunya": ["أبو هريرة"],
            "nisba": [None],
            "laqab": [None],
            "birth_year_ah": [None],
            "death_year_ah": [59],
            "birth_location": [None],
            "death_location": ["Medina"],
            "generation": ["Sahabi"],
            "gender": ["male"],
            "trustworthiness": ["Thiqa"],
            "bio_text": [None],
            "external_id": ["1"],
        }
        table = pa.table(data).cast(NARRATOR_BIO_SCHEMA)
        assert table.num_rows == 1
