"""Parse Fawaz Ahmed hadith edition JSONs into staging Parquet tables.

Each edition JSON contains ``metadata`` and a ``hadiths`` array.
Produces ``hadiths_fawaz.parquet`` and ``collections_fawaz.parquet``.
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


def _parse_edition(
    edition_path: Path,
    info: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Parse a single edition JSON, returning (hadith_rows, collection_row)."""
    with open(edition_path) as f:
        data: dict[str, Any] = json.load(f)

    metadata: dict[str, Any] = data.get("metadata", {})
    hadiths: list[dict[str, Any]] = data.get("hadiths", [])
    edition_key = edition_path.stem  # e.g. "eng-bukhari"
    collection_name = _collection_name_from_key(edition_key)
    sect = _detect_sect(edition_key, metadata)

    hadith_rows: list[dict[str, Any]] = []
    for h in hadiths:
        hadith_number = safe_int(h.get("hadithnumber"))
        source_id = generate_source_id(SOURCE_CORPUS, collection_name, hadith_number or 0)

        grades_raw = h.get("grades", [])
        grade_str = json.dumps(grades_raw) if grades_raw else None

        hadith_rows.append(
            {
                "source_id": source_id,
                "source_corpus": SOURCE_CORPUS,
                "collection_name": collection_name,
                "book_number": None,
                "chapter_number": None,
                "hadith_number": hadith_number,
                "matn_ar": None,
                "matn_en": h.get("text"),
                "isnad_raw_ar": None,
                "isnad_raw_en": None,
                "full_text_ar": None,
                "full_text_en": h.get("text"),
                "grade": grade_str,
                "chapter_name_ar": None,
                "chapter_name_en": None,
                "sect": sect,
            }
        )

    # Build collection row
    collection_row: dict[str, Any] | None = None
    if hadiths:
        collection_row = {
            "collection_id": generate_source_id(SOURCE_CORPUS, collection_name),
            "name_ar": metadata.get("name_ar"),
            "name_en": metadata.get("name", collection_name),
            "compiler_name": metadata.get("author"),
            "compilation_year_ah": None,
            "sect": sect,
            "total_hadiths": len(hadiths),
            "source_corpus": SOURCE_CORPUS,
        }

    return hadith_rows, collection_row


def run(raw_dir: Path, staging_dir: Path) -> tuple[Path, Path]:
    """Parse all Fawaz English editions into staging Parquet files."""
    fawaz_dir = raw_dir / "fawaz"

    # Load editions catalog for enumeration
    editions_path = fawaz_dir / "editions.json"
    with open(editions_path) as f:
        editions_data: dict[str, Any] = json.load(f)

    # Load info.json for grading metadata
    info_path = fawaz_dir / "info.json"
    info: dict[str, Any] = {}
    if info_path.exists():
        with open(info_path) as f:
            info = json.load(f)

    # Filter to English edition keys that have downloaded files
    eng_keys = sorted(k for k in editions_data if k.startswith("eng-"))

    all_hadiths: list[dict[str, Any]] = []
    all_collections: list[dict[str, Any]] = []

    for key in eng_keys:
        edition_file = fawaz_dir / f"{key}.json"
        if not edition_file.exists():
            logger.warning("edition_file_missing", key=key, path=str(edition_file))
            continue

        hadith_rows, collection_row = _parse_edition(edition_file, info)
        all_hadiths.extend(hadith_rows)
        if collection_row is not None:
            all_collections.append(collection_row)

        logger.info(
            "edition_parsed",
            key=key,
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
