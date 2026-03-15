"""Parse Thaqalayn raw JSON into staging Parquet.

Handles two formats:
- **API format**: JSON from ``/api/v2/hadith/{bookId}`` — typically has a
  ``data`` wrapper key with hadith objects.
- **GitHub format**: scraped JSON files from the ThaqalaynAPI repository —
  typically stored as bare arrays or nested differently.

Detection heuristic: if top-level dict contains a ``"data"`` key whose value
is a list, treat as API format. Otherwise treat as GitHub format.
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

SOURCE_CORPUS = "thaqalayn"
SECT = "shia"


def _detect_format(data: Any) -> str:
    """Return 'api' or 'github' based on JSON structure."""
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return "api"
    return "github"


def _extract_hadiths_api(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract hadith list from API-format JSON."""
    result: list[dict[str, Any]] = data.get("data", [])
    return result


def _extract_hadiths_github(data: Any) -> list[dict[str, Any]]:
    """Extract hadith list from GitHub-format JSON."""
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict):
        # Try common wrapper keys
        for key in ("hadiths", "data", "chapters"):
            val = data.get(key)
            if isinstance(val, list):
                return list(val)
        # Might be nested chapters with hadiths
        result: list[dict[str, Any]] = []
        for key, val in data.items():
            if isinstance(val, list):
                result.extend(v for v in val if isinstance(v, dict))
        return result
    return []


def _normalize_grade(raw: Any) -> str | None:
    """Serialize grades to a single string. Arrays or semicolons preserved as JSON."""
    if raw is None:
        return None
    if isinstance(raw, list):
        if len(raw) == 1:
            return safe_str(raw[0])
        return json.dumps(raw, ensure_ascii=False)
    s = safe_str(raw)
    if s and ";" in s:
        parts = [p.strip() for p in s.split(";") if p.strip()]
        if len(parts) > 1:
            return json.dumps(parts, ensure_ascii=False)
    return s


def _hadith_to_row(
    h: dict[str, Any],
    collection_name: str,
    book_number: int | None,
) -> dict[str, Any]:
    """Convert a single hadith dict to a staging row."""
    hadith_num = safe_int(
        h.get("hadithNumber") or h.get("hadith_number") or h.get("number")
    )
    source_id = generate_source_id(
        SOURCE_CORPUS,
        collection_name,
        book_number or 0,
        hadith_num or 0,
    )

    # Isnad/matn: Thaqalayn generally does not separate isnad from matn.
    # If explicit fields exist, use them; otherwise put everything in full_text.
    isnad_ar = safe_str(h.get("isnad") or h.get("isnad_ar"))
    matn_ar = safe_str(h.get("matn") or h.get("matn_ar") or h.get("textAr") or h.get("text_ar"))
    full_ar = safe_str(
        h.get("fullText") or h.get("full_text") or h.get("textAr") or h.get("text_ar")
        or h.get("arabicText") or h.get("arabic")
    )
    matn_en = safe_str(
        h.get("matn_en") or h.get("textEn") or h.get("text_en") or h.get("english")
        or h.get("englishText") or h.get("translation")
    )
    full_en = safe_str(h.get("fullTextEn") or h.get("full_text_en"))
    chapter_ar = safe_str(h.get("chapterAr") or h.get("chapter_ar") or h.get("babAr"))
    chapter_en = safe_str(
        h.get("chapter") or h.get("chapterEn") or h.get("chapter_en") or h.get("babEn")
    )
    chapter_num = safe_int(h.get("chapterNumber") or h.get("chapter_number"))

    grade = _normalize_grade(h.get("grade") or h.get("grading") or h.get("grades"))

    return {
        "source_id": source_id,
        "source_corpus": SOURCE_CORPUS,
        "collection_name": collection_name,
        "book_number": book_number,
        "chapter_number": chapter_num,
        "hadith_number": hadith_num,
        "matn_ar": matn_ar,
        "matn_en": matn_en,
        "isnad_raw_ar": isnad_ar,
        "isnad_raw_en": None,
        "full_text_ar": full_ar,
        "full_text_en": full_en,
        "grade": grade,
        "chapter_name_ar": chapter_ar,
        "chapter_name_en": chapter_en,
        "sect": SECT,
    }


def _infer_collection_name(file_path: Path, data: Any) -> str:
    """Best-effort collection name from file or data."""
    if isinstance(data, dict):
        for key in ("bookName", "book_name", "collection", "title"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    # Fall back to file stem (e.g., "book_123" -> "book_123")
    return file_path.stem


def _infer_book_number(file_path: Path) -> int | None:
    """Extract book number from filename like book_42.json."""
    stem = file_path.stem
    if stem.startswith("book_"):
        return safe_int(stem.removeprefix("book_"))
    return None


def discover(raw_dir: Path) -> None:
    """Load first JSON and log keys/structure for field mapping discovery."""
    thaq_dir = raw_dir / "thaqalayn"
    json_files = sorted(thaq_dir.glob("book_*.json"))
    if not json_files:
        # Try github clone
        json_files = sorted((thaq_dir / "github_clone").rglob("*.json"))

    if not json_files:
        logger.warning("thaqalayn_discover_no_files")
        return

    sample = json_files[0]
    with open(sample, encoding="utf-8") as f:
        data = json.load(f)

    fmt = _detect_format(data)
    logger.info("thaqalayn_discover", file=sample.name, format=fmt)

    if isinstance(data, dict):
        logger.info("thaqalayn_discover_top_keys", keys=list(data.keys()))
        for key, val in data.items():
            if isinstance(val, list) and val:
                first = val[0]
                if isinstance(first, dict):
                    logger.info("thaqalayn_discover_item_keys", parent=key, keys=list(first.keys()))
    elif isinstance(data, list) and data and isinstance(data[0], dict):
        logger.info("thaqalayn_discover_item_keys", parent="root", keys=list(data[0].keys()))


def run(raw_dir: Path, staging_dir: Path) -> tuple[Path, Path]:
    """Parse Thaqalayn JSONs into hadiths + collections Parquet files."""
    thaq_dir = raw_dir / "thaqalayn"

    # Gather JSON files from API download or GitHub clone
    json_files = sorted(thaq_dir.glob("book_*.json"))
    github_jsons: list[Path] = []
    if not json_files:
        github_jsons = sorted((thaq_dir / "github_clone").rglob("*.json"))
        json_files = github_jsons

    if not json_files:
        msg = "No Thaqalayn JSON files found"
        raise FileNotFoundError(msg)

    logger.info("thaqalayn_parse_start", file_count=len(json_files))

    hadith_rows: list[dict[str, Any]] = []
    collections: dict[str, dict[str, Any]] = {}
    total_with_isnad = 0
    total_hadiths = 0

    for fp in json_files:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)

        fmt = _detect_format(data)
        if fmt == "api":
            hadiths = _extract_hadiths_api(data)
        else:
            hadiths = _extract_hadiths_github(data)

        collection_name = _infer_collection_name(fp, data)
        book_number = _infer_book_number(fp)

        for h in hadiths:
            if not isinstance(h, dict):
                continue
            row = _hadith_to_row(h, collection_name, book_number)
            hadith_rows.append(row)
            total_hadiths += 1
            if row["isnad_raw_ar"] is not None:
                total_with_isnad += 1

        # Track collection metadata
        if collection_name not in collections:
            collections[collection_name] = {
                "collection_id": generate_source_id(SOURCE_CORPUS, collection_name),
                "name_ar": safe_str(
                    (data if isinstance(data, dict) else {}).get("bookNameAr")
                    or (data if isinstance(data, dict) else {}).get("book_name_ar")
                ),
                "name_en": collection_name,
                "compiler_name": safe_str(
                    (data if isinstance(data, dict) else {}).get("author")
                    or (data if isinstance(data, dict) else {}).get("compiler")
                ),
                "compilation_year_ah": None,
                "sect": SECT,
                "total_hadiths": 0,
                "source_corpus": SOURCE_CORPUS,
            }
        collections[collection_name]["total_hadiths"] += len(
            [h for h in hadiths if isinstance(h, dict)]
        )

    # Log isnad separation rate
    isnad_rate = (total_with_isnad / total_hadiths * 100) if total_hadiths else 0.0
    logger.info(
        "thaqalayn_isnad_rate",
        total=total_hadiths,
        with_isnad=total_with_isnad,
        rate_pct=round(isnad_rate, 1),
    )

    # Build and write hadiths parquet
    hadith_table = pa.table(
        {field.name: [r[field.name] for r in hadith_rows] for field in HADITH_SCHEMA},
        schema=HADITH_SCHEMA,
    )
    hadiths_path = write_parquet(
        hadith_table, Path(staging_dir) / "hadiths_thaqalayn.parquet", schema=HADITH_SCHEMA
    )

    # Build and write collections parquet
    coll_rows = list(collections.values())
    coll_table = pa.table(
        {field.name: [r[field.name] for r in coll_rows] for field in COLLECTION_SCHEMA},
        schema=COLLECTION_SCHEMA,
    )
    collections_path = write_parquet(
        coll_table, Path(staging_dir) / "collections_thaqalayn.parquet", schema=COLLECTION_SCHEMA
    )

    logger.info(
        "thaqalayn_parse_complete",
        hadiths=len(hadith_rows),
        collections=len(coll_rows),
    )
    return hadiths_path, collections_path
