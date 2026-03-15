"""Parse the LK Hadith Corpus CSVs into staging Parquet files.

Produces three Parquet outputs:
- ``hadiths_lk.parquet`` — all hadiths from 6 books
- ``narrator_mentions_lk.parquet`` — extracted narrator mentions
- ``collections_lk.parquet`` — collection metadata
"""

from __future__ import annotations

import re
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pcsv

from src.parse.base import generate_source_id, read_csv_robust, safe_int, safe_str, write_parquet
from src.parse.narrator_extraction import extract_narrator_mentions
from src.parse.schemas import COLLECTION_SCHEMA, HADITH_SCHEMA, NARRATOR_MENTION_SCHEMA
from src.utils.arabic import normalize_arabic
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Expected 16-column schema from the LK corpus CSVs.
LK_COLUMNS = [
    "Chapter_Number",
    "Chapter_English",
    "Chapter_Arabic",
    "Section_Number",
    "Section_English",
    "Section_Arabic",
    "Hadith_number",
    "English_Hadith",
    "English_Isnad",
    "English_Matn",
    "Arabic_Hadith",
    "Arabic_Isnad",
    "Arabic_Matn",
    "Arabic_Comment",
    "English_Grade",
    "Arabic_Grade",
]

# Filename -> canonical collection name mapping.
FILENAME_TO_COLLECTION: dict[str, str] = {
    "albukhari": "bukhari",
    "almuslim": "muslim",
    "abudawud": "abu_dawud",
    "altirmidhi": "tirmidhi",
    "alnasai": "nasai",
    "ibnmajah": "ibn_majah",
}

# Collection metadata: (name_en, compiler, compilation_year_ah, reference_count).
COLLECTION_META: dict[str, tuple[str, str, int, int]] = {
    "bukhari": ("Sahih al-Bukhari", "Muhammad ibn Ismail al-Bukhari", 256, 7563),
    "muslim": ("Sahih Muslim", "Muslim ibn al-Hajjaj", 261, 7563),
    "abu_dawud": ("Sunan Abu Dawud", "Abu Dawud al-Sijistani", 275, 5274),
    "tirmidhi": ("Jami' al-Tirmidhi", "Abu Isa al-Tirmidhi", 279, 3956),
    "nasai": ("Sunan al-Nasa'i", "Ahmad ibn Shu'ayb al-Nasa'i", 303, 5758),
    "ibn_majah": ("Sunan Ibn Majah", "Ibn Majah al-Qazwini", 273, 4341),
}

# Strip HTML entities/tags.
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ENTITY_RE = re.compile(r"&[a-zA-Z]+;|&#\d+;")


def _strip_html(text: str | None) -> str | None:
    """Remove HTML tags and entities from text."""
    if not text:
        return text
    text = _HTML_TAG_RE.sub("", text)
    text = _HTML_ENTITY_RE.sub("", text)
    return text.strip() or None


def _derive_collection_name(filename: str) -> str | None:
    """Derive canonical collection name from CSV filename."""
    stem = filename.rsplit(".", maxsplit=1)[0].lower()
    return FILENAME_TO_COLLECTION.get(stem)


def _invalid_row_handler(row: pcsv.InvalidRow) -> str:
    """Log and skip invalid CSV rows (equivalent to pandas on_bad_lines='warn')."""
    logger.warning(
        "lk_bad_csv_line",
        row_number=row.number,
        expected_columns=row.expected_columns,
        actual_columns=row.actual_columns,
    )
    return "skip"


def _parse_single_csv(
    csv_path: Path,
    collection_name: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Parse a single LK CSV into hadith rows and narrator mention rows."""
    parse_options = pcsv.ParseOptions(invalid_row_handler=_invalid_row_handler)
    table, _enc = read_csv_robust(csv_path, parse_options=parse_options)

    # Validate column count.
    if len(table.column_names) != len(LK_COLUMNS):
        logger.warning(
            "lk_column_mismatch",
            path=str(csv_path),
            expected=len(LK_COLUMNS),
            actual=len(table.column_names),
        )
    # Re-assign column names from schema if column count matches.
    if len(table.column_names) == len(LK_COLUMNS):
        table = table.rename_columns(LK_COLUMNS)

    hadith_rows: list[dict[str, object]] = []
    mention_rows: list[dict[str, object]] = []

    for row in table.to_pylist():
        chapter_num = safe_int(row.get("Chapter_Number"))
        section_num = safe_int(row.get("Section_Number"))
        hadith_num = safe_int(row.get("Hadith_number"))

        source_id = generate_source_id(
            "lk",
            collection_name,
            chapter_num if chapter_num is not None else 0,
            hadith_num if hadith_num is not None else 0,
        )

        en_grade = safe_str(row.get("English_Grade"))
        ar_grade = safe_str(row.get("Arabic_Grade"))
        grade = en_grade or ar_grade

        hadith_rows.append({
            "source_id": source_id,
            "source_corpus": "lk",
            "collection_name": collection_name,
            "book_number": chapter_num,
            "chapter_number": section_num,
            "hadith_number": hadith_num,
            "matn_ar": _strip_html(safe_str(row.get("Arabic_Matn"))),
            "matn_en": _strip_html(safe_str(row.get("English_Matn"))),
            "isnad_raw_ar": _strip_html(safe_str(row.get("Arabic_Isnad"))),
            "isnad_raw_en": _strip_html(safe_str(row.get("English_Isnad"))),
            "full_text_ar": _strip_html(safe_str(row.get("Arabic_Hadith"))),
            "full_text_en": _strip_html(safe_str(row.get("English_Hadith"))),
            "grade": grade,
            "chapter_name_ar": safe_str(row.get("Chapter_Arabic")),
            "chapter_name_en": safe_str(row.get("Chapter_English")),
            "sect": "sunni",
        })

        # Extract narrator mentions from English isnad.
        en_isnad = safe_str(row.get("English_Isnad"))
        if en_isnad:
            for span in extract_narrator_mentions(_strip_html(en_isnad) or "", "en"):
                mention_id = f"{source_id}:en:{span.position}"
                mention_rows.append({
                    "mention_id": mention_id,
                    "source_hadith_id": source_id,
                    "source_corpus": "lk",
                    "position_in_chain": span.position,
                    "name_ar": None,
                    "name_en": span.name,
                    "name_ar_normalized": None,
                    "transmission_method": span.transmission_method,
                })

        # Extract narrator mentions from Arabic isnad.
        ar_isnad = safe_str(row.get("Arabic_Isnad"))
        if ar_isnad:
            for span in extract_narrator_mentions(_strip_html(ar_isnad) or "", "ar"):
                mention_id = f"{source_id}:ar:{span.position}"
                mention_rows.append({
                    "mention_id": mention_id,
                    "source_hadith_id": source_id,
                    "source_corpus": "lk",
                    "position_in_chain": span.position,
                    "name_ar": span.name,
                    "name_en": None,
                    "name_ar_normalized": normalize_arabic(span.name),
                    "transmission_method": span.transmission_method,
                })

    return hadith_rows, mention_rows


def _log_grade_coverage(hadith_rows: list[dict[str, object]]) -> None:
    """Log grade coverage statistics."""
    total = len(hadith_rows)
    if total == 0:
        return
    en_grades = sum(1 for r in hadith_rows if safe_str(r.get("grade")))
    ar_isnads = sum(1 for r in hadith_rows if r.get("isnad_raw_ar"))
    en_isnads = sum(1 for r in hadith_rows if r.get("isnad_raw_en"))
    logger.info(
        "lk_grade_coverage",
        total=total,
        with_grade=en_grades,
        with_ar_isnad=ar_isnads,
        with_en_isnad=en_isnads,
        grade_pct=round(100 * en_grades / total, 1),
    )


def run(raw_dir: Path, staging_dir: Path) -> list[Path]:
    """Parse all LK corpus CSVs and write staging Parquet files."""
    lk_dir = raw_dir / "lk"
    csv_files = sorted(lk_dir.rglob("*.csv"))
    if not csv_files:
        msg = f"No CSV files found in {lk_dir}"
        raise FileNotFoundError(msg)

    all_hadiths: list[dict[str, object]] = []
    all_mentions: list[dict[str, object]] = []
    collection_rows: list[dict[str, object]] = []

    for csv_path in csv_files:
        collection_name = _derive_collection_name(csv_path.name)
        if collection_name is None:
            logger.warning("lk_unknown_csv", path=str(csv_path))
            continue

        logger.info("lk_parsing", file=csv_path.name, collection=collection_name)
        hadith_rows, mention_rows = _parse_single_csv(csv_path, collection_name)
        all_hadiths.extend(hadith_rows)
        all_mentions.extend(mention_rows)

        # Build collection metadata with actual row count.
        meta = COLLECTION_META.get(collection_name)
        actual_count = len(hadith_rows)
        if meta:
            name_en, compiler, year_ah, ref_count = meta
            # Sanity-check: warn if actual count differs by more than 20% from reference.
            if ref_count > 0 and abs(actual_count - ref_count) / ref_count > 0.2:
                logger.warning(
                    "lk_count_mismatch",
                    collection=collection_name,
                    actual=actual_count,
                    reference=ref_count,
                )
            collection_rows.append({
                "collection_id": f"lk:{collection_name}",
                "name_ar": None,
                "name_en": name_en,
                "compiler_name": compiler,
                "compilation_year_ah": year_ah,
                "sect": "sunni",
                "total_hadiths": actual_count,
                "source_corpus": "lk",
            })

        if collection_name == "bukhari":
            logger.info("lk_bukhari_gold_standard", row_count=actual_count)

    _log_grade_coverage(all_hadiths)

    # Write Parquet files.
    staging_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []

    hadith_table = pa.Table.from_pylist(all_hadiths)
    output_paths.append(
        write_parquet(hadith_table, staging_dir / "hadiths_lk.parquet", schema=HADITH_SCHEMA)
    )

    if all_mentions:
        mention_table = pa.Table.from_pylist(all_mentions)
        output_paths.append(
            write_parquet(
                mention_table,
                staging_dir / "narrator_mentions_lk.parquet",
                schema=NARRATOR_MENTION_SCHEMA,
            )
        )

    if collection_rows:
        coll_table = pa.Table.from_pylist(collection_rows)
        output_paths.append(
            write_parquet(
                coll_table,
                staging_dir / "collections_lk.parquet",
                schema=COLLECTION_SCHEMA,
            )
        )

    logger.info(
        "lk_parse_complete",
        total_hadiths=len(all_hadiths),
        total_mentions=len(all_mentions),
        collections=len(collection_rows),
    )
    return output_paths
