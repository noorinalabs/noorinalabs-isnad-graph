"""Parse Open Hadith Data CSVs into staging Parquet.

Reads with-diacritics CSV files (detected by "tashkeel" or "diacritics" in the
filename). Each CSV may have a different schema depending on the book, so we
inspect headers and map columns dynamically.
"""

from __future__ import annotations

import re
from pathlib import Path

import pyarrow as pa

from src.parse.base import (
    generate_source_id,
    read_csv_robust,
    safe_int,
    safe_str,
    write_parquet,
)
from src.parse.schemas import HADITH_SCHEMA
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Patterns indicating a diacritics/tashkeel file.
_DIACRITICS_RE = re.compile(r"tashkeel|diacritics", re.IGNORECASE)

# Common column name mappings (lowercase -> canonical).
_TEXT_COLUMNS = {"hadith", "text", "matn", "content", "hadith_text", "حديث", "متن"}
_NUMBER_COLUMNS = {"hadith_number", "number", "hadith_no", "رقم", "id"}
_BOOK_COLUMNS = {"book_number", "book", "book_no", "كتاب"}
_CHAPTER_COLUMNS = {"chapter", "chapter_number", "chapter_no", "باب"}


def _find_column(headers: list[str], candidates: set[str]) -> str | None:
    """Find the first header matching any candidate (case-insensitive)."""
    lower_map = {h.lower().strip(): h for h in headers}
    for candidate in candidates:
        if candidate in lower_map:
            return lower_map[candidate]
    return None


def _collection_name_from_path(csv_path: Path) -> str:
    """Derive a collection name from the file path."""
    stem = csv_path.stem
    # Remove tashkeel/diacritics suffix to get clean book name.
    cleaned = re.sub(r"[-_]?(tashkeel|diacritics|with[-_]?diacritics)", "", stem, flags=re.I)
    cleaned = cleaned.strip("-_ ")
    return cleaned or stem


def run(raw_dir: Path, staging_dir: Path) -> Path:
    """Parse Open Hadith diacritics CSVs into hadiths_open_hadith.parquet."""
    source_dir = raw_dir / "open_hadith"
    if not source_dir.exists():
        msg = f"Source directory not found: {source_dir}"
        raise FileNotFoundError(msg)

    # Find diacritics CSV files.
    all_csvs = list(source_dir.rglob("*.csv"))
    diacritics_csvs = [p for p in all_csvs if _DIACRITICS_RE.search(p.name)]

    if not diacritics_csvs:
        logger.warning("no_diacritics_csvs_found", total_csvs=len(all_csvs))
        # Fall back to all CSVs if no diacritics-specific files found.
        diacritics_csvs = all_csvs

    logger.info("open_hadith_csvs_found", count=len(diacritics_csvs))

    rows: list[dict[str, str | int | None]] = []

    for csv_path in sorted(diacritics_csvs):
        collection = _collection_name_from_path(csv_path)
        try:
            table, _enc = read_csv_robust(csv_path)
        except Exception:
            logger.warning("csv_read_failed", path=str(csv_path))
            continue

        headers = table.column_names
        text_col = _find_column(headers, _TEXT_COLUMNS)
        number_col = _find_column(headers, _NUMBER_COLUMNS)
        book_col = _find_column(headers, _BOOK_COLUMNS)
        chapter_col = _find_column(headers, _CHAPTER_COLUMNS)

        # Convert columns to Python lists once (avoid O(n^2) per-row conversion).
        number_vals = table.column(number_col).to_pylist() if number_col else None
        text_vals = table.column(text_col).to_pylist() if text_col else None
        book_vals = table.column(book_col).to_pylist() if book_col else None
        chapter_vals = table.column(chapter_col).to_pylist() if chapter_col else None

        for i in range(table.num_rows):
            hadith_num = safe_int(number_vals[i]) if number_vals is not None else i + 1
            text_value = safe_str(text_vals[i]) if text_vals is not None else None
            book_num = safe_int(book_vals[i]) if book_vals is not None else None
            chapter_num = safe_int(chapter_vals[i]) if chapter_vals is not None else None

            source_id = generate_source_id("open_hadith", collection, hadith_num or (i + 1))

            rows.append(
                {
                    "source_id": source_id,
                    "source_corpus": "open_hadith",
                    "collection_name": collection,
                    "book_number": book_num,
                    "chapter_number": chapter_num,
                    "hadith_number": hadith_num,
                    "matn_ar": text_value,
                    "matn_en": None,
                    "isnad_raw_ar": None,
                    "isnad_raw_en": None,
                    "full_text_ar": text_value if text_col is None else None,
                    "full_text_en": None,
                    "grade": None,
                    "chapter_name_ar": None,
                    "chapter_name_en": None,
                    "sect": "sunni",
                }
            )

        logger.info(
            "open_hadith_csv_parsed",
            collection=collection,
            rows=table.num_rows,
            text_col=text_col,
        )

    if not rows:
        msg = "No hadith rows parsed from Open Hadith Data"
        raise ValueError(msg)

    # Build PyArrow table from row dicts.
    arrays = {field.name: [r[field.name] for r in rows] for field in HADITH_SCHEMA}
    out_table = pa.table(arrays, schema=HADITH_SCHEMA)

    out_path = staging_dir / "hadiths_open_hadith.parquet"
    write_parquet(out_table, out_path, schema=HADITH_SCHEMA)
    logger.info("open_hadith_parsed", total_hadiths=len(rows))
    return out_path
