"""Parse Sunnah.com API raw JSON into staging Parquet tables.

Produces ``hadiths_sunnah.parquet`` and ``collections_sunnah.parquet``.
Gracefully skips if raw data is missing (source was not acquired).
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


def _extract_text(hadith: dict[str, Any], lang: str) -> str | None:
    """Extract body text for a language from language-keyed fields.

    The Sunnah.com API may nest text under keys like ``"hadith"`` with
    sub-objects keyed by language (``"ar"``, ``"en"``), or expose ``"body"``
    directly.  Try common patterns.
    """
    # Pattern 1: top-level language-keyed list
    for entry in hadith.get("hadith", []):
        if isinstance(entry, dict) and entry.get("lang") == lang:
            return safe_str(entry.get("body"))

    # Pattern 2: direct body field (single-language endpoint)
    if lang == "en":
        body = safe_str(hadith.get("body"))
        if body:
            return body

    return None


def _serialize_grades(hadith: dict[str, Any]) -> str | None:
    """Serialize grades array to a JSON string, or return single grade."""
    grades = hadith.get("grades") or hadith.get("grade")
    if not grades:
        return None
    if isinstance(grades, list):
        if len(grades) == 1:
            return safe_str(grades[0].get("grade", str(grades[0])))
        return json.dumps(grades, ensure_ascii=False)
    return safe_str(grades)


def run(raw_dir: Path, staging_dir: Path) -> list[Path]:
    """Parse Sunnah.com raw JSON into staging Parquet files.

    Returns list of written Parquet paths (empty if source was skipped).
    """
    sunnah_dir = raw_dir / "sunnah"
    collections_path = sunnah_dir / "collections.json"

    if not collections_path.exists():
        logger.info("sunnah_parse_skipped", reason="raw data missing (source not acquired)")
        return []

    # Load collection metadata
    with open(collections_path, encoding="utf-8") as f:
        raw_collections: list[dict[str, Any]] = json.load(f)

    # Build collection records
    collection_rows: list[dict[str, Any]] = []
    for coll in raw_collections:
        name = coll.get("name", coll.get("collection", ""))
        if not name:
            continue
        collection_rows.append({
            "collection_id": generate_source_id(SOURCE_CORPUS, name),
            "name_ar": safe_str(coll.get("collection", [{}])[0].get("title"))
            if isinstance(coll.get("collection"), list)
            else safe_str(coll.get("title")),
            "name_en": name,
            "compiler_name": safe_str(coll.get("shortIntro"))
            if isinstance(coll.get("shortIntro"), str)
            else None,
            "compilation_year_ah": None,
            "sect": SECT,
            "total_hadiths": safe_int(coll.get("totalHadith", coll.get("hadithsCount"))),
            "source_corpus": SOURCE_CORPUS,
        })

    # Parse hadiths per collection
    hadith_rows: list[dict[str, Any]] = []
    for coll in raw_collections:
        name = coll.get("name", coll.get("collection", ""))
        if not name:
            continue

        hadiths_path = sunnah_dir / f"{name}_hadiths.json"
        if not hadiths_path.exists():
            logger.warning("sunnah_hadiths_missing", collection=name)
            continue

        with open(hadiths_path, encoding="utf-8") as f:
            hadiths: list[dict[str, Any]] = json.load(f)

        for h in hadiths:
            hadith_number = safe_int(h.get("hadithNumber"))
            book_number = safe_int(h.get("bookNumber"))
            chapter_number = safe_int(h.get("chapterNumber"))

            source_id = generate_source_id(
                SOURCE_CORPUS,
                name,
                book_number or 0,
                hadith_number or 0,
            )

            hadith_rows.append({
                "source_id": source_id,
                "source_corpus": SOURCE_CORPUS,
                "collection_name": name,
                "book_number": book_number,
                "chapter_number": chapter_number,
                "hadith_number": hadith_number,
                "matn_ar": _extract_text(h, "ar"),
                "matn_en": _extract_text(h, "en"),
                "isnad_raw_ar": None,
                "isnad_raw_en": None,
                "full_text_ar": _extract_text(h, "ar"),
                "full_text_en": _extract_text(h, "en"),
                "grade": _serialize_grades(h),
                "chapter_name_ar": None,
                "chapter_name_en": safe_str(h.get("chapterTitle")),
                "sect": SECT,
            })

    output_files: list[Path] = []

    if hadith_rows:
        hadith_table = pa.table(
            {field.name: [r[field.name] for r in hadith_rows] for field in HADITH_SCHEMA},
        )
        hadith_path = write_parquet(
            hadith_table, staging_dir / "hadiths_sunnah.parquet", HADITH_SCHEMA
        )
        output_files.append(hadith_path)
        logger.info("sunnah_hadiths_parsed", count=len(hadith_rows))

    if collection_rows:
        collection_table = pa.table(
            {field.name: [r[field.name] for r in collection_rows] for field in COLLECTION_SCHEMA},
        )
        collection_path = write_parquet(
            collection_table, staging_dir / "collections_sunnah.parquet", COLLECTION_SCHEMA
        )
        output_files.append(collection_path)
        logger.info("sunnah_collections_parsed", count=len(collection_rows))

    return output_files
