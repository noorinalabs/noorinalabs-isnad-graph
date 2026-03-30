"""Parse sunnah.com scraped JSON into staging Parquet tables.

Produces ``hadiths_sunnah_scraped.parquet`` and ``collections_sunnah_scraped.parquet``.
Uses ``source_corpus = "sunnah"`` for dedup compatibility with the API-sourced data.
Gracefully skips if raw data is missing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa

from src.parse.base import generate_source_id, safe_int, safe_str, write_parquet
from src.parse.schemas import COLLECTION_SCHEMA, HADITH_SCHEMA
from src.utils.logging import get_logger

logger = get_logger(__name__)

SOURCE_CORPUS = "sunnah"
SECT = "sunni"


def run(raw_dir: Path, staging_dir: Path) -> list[Path]:
    """Parse sunnah.com scraped JSON into staging Parquet files.

    Returns list of written Parquet paths (empty if source was skipped).
    """
    scraped_dir = raw_dir / "sunnah_scraped"

    if not scraped_dir.exists():
        logger.info("sunnah_scraped_parse_skipped", reason="raw data missing (source not acquired)")
        return []

    json_files = sorted(scraped_dir.glob("*.json"))
    # Filter out manifest.json and progress files
    json_files = [f for f in json_files if f.name != "manifest.json" and not f.name.startswith(".")]

    if not json_files:
        logger.info("sunnah_scraped_parse_skipped", reason="no JSON files found")
        return []

    collection_rows: list[dict[str, Any]] = []
    hadith_rows: list[dict[str, Any]] = []

    for json_path in json_files:
        collection_name = json_path.stem  # e.g. "musnad-ahmad"

        with open(json_path, encoding="utf-8") as f:
            hadiths: list[dict[str, Any]] = json.load(f)

        # Build collection record
        collection_rows.append(
            {
                "collection_id": generate_source_id(SOURCE_CORPUS, collection_name),
                "name_ar": None,
                "name_en": collection_name,
                "compiler_name": None,
                "compilation_year_ah": None,
                "sect": SECT,
                "total_hadiths": len(hadiths),
                "source_corpus": SOURCE_CORPUS,
            }
        )

        # Build hadith records
        for h in hadiths:
            hadith_number = safe_int(h.get("hadith_number"))
            book_number = safe_int(h.get("book_number"))
            chapter_number = safe_int(h.get("chapter_number"))

            source_id = generate_source_id(
                SOURCE_CORPUS,
                collection_name,
                book_number or 0,
                chapter_number or 0,
                hadith_number or 0,
            )

            hadith_rows.append(
                {
                    "source_id": source_id,
                    "source_corpus": SOURCE_CORPUS,
                    "collection_name": collection_name,
                    "book_number": book_number,
                    "chapter_number": chapter_number,
                    "hadith_number": hadith_number,
                    "matn_ar": safe_str(h.get("text_ar")),
                    "matn_en": safe_str(h.get("text_en")),
                    "isnad_raw_ar": None,
                    "isnad_raw_en": None,
                    "full_text_ar": safe_str(h.get("text_ar")),
                    "full_text_en": safe_str(h.get("text_en")),
                    "grade": safe_str(h.get("grade")),
                    "chapter_name_ar": safe_str(h.get("chapter_name_ar")),
                    "chapter_name_en": safe_str(h.get("chapter_name_en")),
                    "sect": SECT,
                }
            )

    output_files: list[Path] = []

    if hadith_rows:
        hadith_table = pa.table(
            {field.name: [r[field.name] for r in hadith_rows] for field in HADITH_SCHEMA},
        )
        hadith_path = write_parquet(
            hadith_table, staging_dir / "hadiths_sunnah_scraped.parquet", HADITH_SCHEMA
        )
        output_files.append(hadith_path)
        logger.info("sunnah_scraped_hadiths_parsed", count=len(hadith_rows))

    if collection_rows:
        collection_table = pa.table(
            {field.name: [r[field.name] for r in collection_rows] for field in COLLECTION_SCHEMA},
        )
        collection_path = write_parquet(
            collection_table, staging_dir / "collections_sunnah_scraped.parquet", COLLECTION_SCHEMA
        )
        output_files.append(collection_path)
        logger.info("sunnah_scraped_collections_parsed", count=len(collection_rows))

    return output_files
