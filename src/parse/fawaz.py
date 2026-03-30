"""Parse Fawaz Ahmed hadith edition JSONs into staging Parquet tables.

Each edition JSON contains ``metadata`` and a ``hadiths`` array.
Produces ``hadiths_fawaz.parquet`` and ``collections_fawaz.parquet``.

English (eng-*) and Arabic (ara-*) editions are merged by hadith number
within each collection to produce parallel text records.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa

from src.parse.base import generate_source_id, safe_int, write_parquet
from src.parse.schemas import COLLECTION_SCHEMA, HADITH_SCHEMA
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Edition name substrings that indicate Shia sources.
_SHIA_INDICATORS = frozenset(
    {
        "nahj",
        "kafi",
        "tahdhib",
        "istibsar",
        "man-la",
    }
)

SOURCE_CORPUS = "fawaz"


def _detect_sect(edition_key: str, metadata: dict[str, Any]) -> str:
    """Return ``'shia'`` if the edition name suggests a Shia collection."""
    name_lower = metadata.get("name", "").lower() + " " + edition_key.lower()
    for indicator in _SHIA_INDICATORS:
        if indicator in name_lower:
            return "shia"
    return "sunni"


def _collection_name_from_key(edition_key: str) -> str:
    """Derive a human-readable collection name from the edition key.

    Example: ``eng-bukhari`` -> ``bukhari``
    """
    # Strip language prefix (e.g. "eng-")
    parts = edition_key.split("-", 1)
    return parts[1] if len(parts) > 1 else edition_key


def _load_edition(edition_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load an edition JSON, returning (metadata, hadiths)."""
    with open(edition_path) as f:
        data: dict[str, Any] = json.load(f)
    return data.get("metadata", {}), data.get("hadiths", [])


def _merge_editions(
    eng_hadiths: list[dict[str, Any]],
    ara_hadiths: list[dict[str, Any]],
    collection_name: str,
    metadata: dict[str, Any],
    sect: str,
) -> list[dict[str, Any]]:
    """Merge English and Arabic hadith lists by hadith number."""
    # Index Arabic hadiths by number
    ara_by_number: dict[int | None, dict[str, Any]] = {}
    for h in ara_hadiths:
        num = safe_int(h.get("hadithnumber"))
        ara_by_number[num] = h

    # Track which Arabic hadiths were matched
    matched_ara_numbers: set[int | None] = set()
    rows: list[dict[str, Any]] = []

    # Process English hadiths, merging Arabic where available
    for h in eng_hadiths:
        hadith_number = safe_int(h.get("hadithnumber"))
        source_id = generate_source_id(SOURCE_CORPUS, collection_name, hadith_number or 0)

        grades_raw = h.get("grades", [])
        grade_str = json.dumps(grades_raw) if grades_raw else None

        ara_match = ara_by_number.get(hadith_number)
        matn_ar = ara_match.get("text") if ara_match else None
        if ara_match:
            matched_ara_numbers.add(hadith_number)

        rows.append(
            {
                "source_id": source_id,
                "source_corpus": SOURCE_CORPUS,
                "collection_name": collection_name,
                "book_number": None,
                "chapter_number": None,
                "hadith_number": hadith_number,
                "matn_ar": matn_ar,
                "matn_en": h.get("text"),
                "isnad_raw_ar": None,
                "isnad_raw_en": None,
                "full_text_ar": matn_ar,
                "full_text_en": h.get("text"),
                "grade": grade_str,
                "chapter_name_ar": None,
                "chapter_name_en": None,
                "sect": sect,
            }
        )

    # Process Arabic-only hadiths (no English counterpart)
    for h in ara_hadiths:
        hadith_number = safe_int(h.get("hadithnumber"))
        if hadith_number in matched_ara_numbers:
            continue

        logger.warning(
            "arabic_only_hadith",
            collection=collection_name,
            hadith_number=hadith_number,
        )

        source_id = generate_source_id(SOURCE_CORPUS, collection_name, hadith_number or 0)
        grades_raw = h.get("grades", [])
        grade_str = json.dumps(grades_raw) if grades_raw else None

        rows.append(
            {
                "source_id": source_id,
                "source_corpus": SOURCE_CORPUS,
                "collection_name": collection_name,
                "book_number": None,
                "chapter_number": None,
                "hadith_number": hadith_number,
                "matn_ar": h.get("text"),
                "matn_en": None,
                "isnad_raw_ar": None,
                "isnad_raw_en": None,
                "full_text_ar": h.get("text"),
                "full_text_en": None,
                "grade": grade_str,
                "chapter_name_ar": None,
                "chapter_name_en": None,
                "sect": sect,
            }
        )

    return rows


def run(raw_dir: Path, staging_dir: Path) -> tuple[Path, Path]:
    """Parse all Fawaz English + Arabic editions into staging Parquet files."""
    fawaz_dir = raw_dir / "fawaz"

    # Enumerate edition files from the directory rather than editions.json,
    # because editions.json uses collection-level keys (e.g. "bukhari") while
    # the actual files use lang-prefixed names (e.g. "eng-bukhari.json").
    eng_keys = sorted(p.stem for p in fawaz_dir.glob("eng-*.json"))
    ara_keys_set = {p.stem for p in fawaz_dir.glob("ara-*.json")}

    all_hadiths: list[dict[str, Any]] = []
    all_collections: list[dict[str, Any]] = []

    for eng_key in eng_keys:
        collection_name = _collection_name_from_key(eng_key)
        ara_key = f"ara-{collection_name}"

        eng_file = fawaz_dir / f"{eng_key}.json"
        if not eng_file.exists():
            logger.warning("edition_file_missing", key=eng_key, path=str(eng_file))
            continue

        eng_metadata, eng_hadiths = _load_edition(eng_file)
        sect = _detect_sect(eng_key, eng_metadata)

        # Load Arabic edition if available
        ara_hadiths: list[dict[str, Any]] = []
        ara_file = fawaz_dir / f"{ara_key}.json"
        if ara_key in ara_keys_set and ara_file.exists():
            _, ara_hadiths = _load_edition(ara_file)
            logger.info(
                "arabic_edition_loaded",
                key=ara_key,
                hadiths=len(ara_hadiths),
            )
        else:
            logger.warning("arabic_edition_missing", collection=collection_name)

        # Log English hadiths that have no Arabic match
        if ara_hadiths:
            ara_numbers = {safe_int(h.get("hadithnumber")) for h in ara_hadiths}
            for h in eng_hadiths:
                num = safe_int(h.get("hadithnumber"))
                if num not in ara_numbers:
                    logger.warning(
                        "english_only_hadith",
                        collection=collection_name,
                        hadith_number=num,
                    )

        hadith_rows = _merge_editions(eng_hadiths, ara_hadiths, collection_name, eng_metadata, sect)
        all_hadiths.extend(hadith_rows)

        if eng_hadiths or ara_hadiths:
            collection_row = {
                "collection_id": generate_source_id(SOURCE_CORPUS, collection_name),
                "name_ar": eng_metadata.get("name_ar"),
                "name_en": eng_metadata.get("name", collection_name),
                "compiler_name": eng_metadata.get("author"),
                "compilation_year_ah": None,
                "sect": sect,
                "total_hadiths": len(hadith_rows),
                "source_corpus": SOURCE_CORPUS,
            }
            all_collections.append(collection_row)

        logger.info(
            "edition_parsed",
            key=eng_key,
            hadiths=len(hadith_rows),
        )

    # Write hadiths parquet
    hadiths_table = pa.table(
        {field.name: [r[field.name] for r in all_hadiths] for field in HADITH_SCHEMA},
        schema=HADITH_SCHEMA,
    )
    hadiths_path = write_parquet(hadiths_table, staging_dir / "hadiths_fawaz.parquet")

    # Write collections parquet
    collections_table = pa.table(
        {field.name: [r[field.name] for r in all_collections] for field in COLLECTION_SCHEMA},
        schema=COLLECTION_SCHEMA,
    )
    collections_path = write_parquet(collections_table, staging_dir / "collections_fawaz.parquet")

    logger.info(
        "fawaz_parse_complete",
        total_hadiths=len(all_hadiths),
        total_collections=len(all_collections),
    )
    return hadiths_path, collections_path
