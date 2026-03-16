"""Shared test fixture factories for building Parquet tables with sensible defaults.

Avoids duplicating full HADITH_SCHEMA column construction across test files.
"""

from __future__ import annotations

from typing import Any

import pyarrow as pa

from src.parse.schemas import HADITH_SCHEMA


def build_hadith_table(overrides: list[dict[str, Any]] | None = None) -> pa.Table:
    """Build a hadith Parquet table with sensible defaults.

    Each dict in *overrides* represents one row. Only fields that differ from
    the defaults need to be specified.

    Example::

        table = build_hadith_table([
            {"source_id": "h-1", "matn_ar": "text"},
            {"source_id": "h-2", "sect": "shia"},
        ])
    """
    defaults: dict[str, Any] = {
        "source_id": "h-0",
        "source_corpus": "sunnah",
        "collection_name": "bukhari",
        "book_number": 1,
        "chapter_number": 1,
        "hadith_number": 1,
        "matn_ar": "إنما الأعمال بالنيات",
        "matn_en": "Actions are judged by intentions",
        "isnad_raw_ar": None,
        "isnad_raw_en": None,
        "full_text_ar": None,
        "full_text_en": None,
        "grade": None,
        "chapter_name_ar": None,
        "chapter_name_en": None,
        "sect": "sunni",
    }

    if overrides is None:
        overrides = [{}]

    rows: list[dict[str, Any]] = []
    for i, ovr in enumerate(overrides):
        row = {**defaults, **ovr}
        if row["source_id"] == "h-0" and "source_id" not in ovr:
            row["source_id"] = f"h-{i + 1}"
        rows.append(row)

    columns: dict[str, pa.Array] = {}
    type_map: dict[str, pa.DataType] = {f.name: f.type for f in HADITH_SCHEMA}

    for field_name in defaults:
        values = [r[field_name] for r in rows]
        columns[field_name] = pa.array(values, type=type_map[field_name])

    return pa.table(columns, schema=HADITH_SCHEMA)
