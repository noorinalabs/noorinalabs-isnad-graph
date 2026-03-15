"""Shared fixtures for tests/test_resolve/."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.parse.schemas import HADITH_SCHEMA


def write_hadiths(path: Path, rows: list[dict]) -> Path:
    """Write a hadiths Parquet file with HADITH_SCHEMA from a list of row dicts."""
    arrays = {
        "source_id": pa.array([r["source_id"] for r in rows], type=pa.string()),
        "source_corpus": pa.array([r["source_corpus"] for r in rows], type=pa.string()),
        "collection_name": pa.array(
            [r["collection_name"] for r in rows], type=pa.string()
        ),
        "book_number": pa.array([r.get("book_number") for r in rows], type=pa.int32()),
        "chapter_number": pa.array(
            [r.get("chapter_number") for r in rows], type=pa.int32()
        ),
        "hadith_number": pa.array(
            [r.get("hadith_number") for r in rows], type=pa.int32()
        ),
        "matn_ar": pa.array([r.get("matn_ar") for r in rows], type=pa.string()),
        "matn_en": pa.array([r.get("matn_en") for r in rows], type=pa.string()),
        "isnad_raw_ar": pa.array([r.get("isnad_raw_ar") for r in rows], type=pa.string()),
        "isnad_raw_en": pa.array([r.get("isnad_raw_en") for r in rows], type=pa.string()),
        "full_text_ar": pa.array([r.get("full_text_ar") for r in rows], type=pa.string()),
        "full_text_en": pa.array([r.get("full_text_en") for r in rows], type=pa.string()),
        "grade": pa.array([r.get("grade") for r in rows], type=pa.string()),
        "chapter_name_ar": pa.array(
            [r.get("chapter_name_ar") for r in rows], type=pa.string()
        ),
        "chapter_name_en": pa.array(
            [r.get("chapter_name_en") for r in rows], type=pa.string()
        ),
        "sect": pa.array([r["sect"] for r in rows], type=pa.string()),
    }
    table = pa.table(arrays, schema=HADITH_SCHEMA)
    pq.write_table(table, path)
    return path
