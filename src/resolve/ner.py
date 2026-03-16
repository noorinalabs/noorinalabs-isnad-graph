"""Narrator Named Entity Recognition from isnad chains.

Reads all staging Parquet files and consolidates narrator mentions into a
single ``narrator_mentions_resolved.parquet`` for downstream disambiguation.

Sources with Phase 1 narrator mentions (sanadset, lk) are reused directly.
Arabic-text sources (thaqalayn, open_hadith) use rule-based extraction.
English-only sources (fawaz, sunnah) use keyword-based extraction.
Muhaddithat is skipped (bio/network data only, no raw isnads).
"""

from __future__ import annotations

import csv
import random
import uuid
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.parse.base import safe_str, write_parquet
from src.parse.narrator_extraction import extract_narrator_mentions
from src.resolve.schemas import NARRATOR_MENTIONS_RESOLVED_SCHEMA
from src.utils.arabic import is_arabic, normalize_arabic
from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["run"]

# Sources that already have Phase 1 narrator_mentions Parquet files.
_PHASE1_MENTION_SOURCES: dict[str, str] = {
    "sanadset": "narrator_mentions_sanadset.parquet",
    "lk": "narrator_mentions_lk.parquet",
}

# Sources with Arabic isnads needing rule-based extraction.
_ARABIC_SOURCES: set[str] = {"thaqalayn", "open_hadith"}

# Sources with English text needing keyword-based extraction.
_ENGLISH_SOURCES: set[str] = {"fawaz", "sunnah"}

# Sources to skip entirely (no raw isnads).
_SKIP_SOURCES: set[str] = {"muhaddithat"}


def _load_phase1_mentions(
    staging_dir: Path,
    corpus: str,
    filename: str,
) -> list[dict[str, str | int | None]]:
    """Load pre-extracted Phase 1 narrator mentions and map to resolved schema."""
    path = staging_dir / filename
    if not path.exists():
        logger.warning("phase1_mentions_missing", corpus=corpus, path=str(path))
        return []

    table = pq.read_table(path)
    rows: list[dict[str, str | int | None]] = []

    for i in range(table.num_rows):
        name_ar = safe_str(table.column("name_ar")[i].as_py())
        name_en = safe_str(table.column("name_en")[i].as_py())
        name_ar_norm = safe_str(table.column("name_ar_normalized")[i].as_py())

        # Use Arabic name if available, else English.
        name_raw = name_ar or name_en
        name_normalized = name_ar_norm or (normalize_arabic(name_ar) if name_ar else name_en)

        rows.append(
            {
                "mention_id": str(uuid.uuid4()),
                "hadith_id": table.column("source_hadith_id")[i].as_py(),
                "source_corpus": corpus,
                "position_in_chain": table.column("position_in_chain")[i].as_py(),
                "name_raw": name_raw,
                "name_normalized": name_normalized,
                "canonical_narrator_id": None,
                "transmission_method": safe_str(table.column("transmission_method")[i].as_py()),
                "confidence": None,
            }
        )

    logger.info("phase1_mentions_loaded", corpus=corpus, mentions=len(rows))
    return rows


def _extract_from_hadiths(
    staging_dir: Path,
    corpus: str,
    language: str,
) -> list[dict[str, str | int | None]]:
    """Extract narrator mentions from hadith Parquet files for a given corpus."""
    pattern = f"hadiths_{corpus}*.parquet"
    hadith_files = sorted(staging_dir.glob(pattern))
    if not hadith_files:
        logger.warning("no_hadith_files", corpus=corpus, pattern=pattern)
        return []

    rows: list[dict[str, str | int | None]] = []
    null_isnad_count = 0
    total_hadiths = 0

    for hf in hadith_files:
        table = pq.read_table(hf)
        total_hadiths += table.num_rows

        isnad_col = "isnad_raw_ar" if language == "ar" else "isnad_raw_en"
        text_col = "full_text_ar" if language == "ar" else "full_text_en"

        for i in range(table.num_rows):
            hadith_id = table.column("source_id")[i].as_py()
            isnad_text = safe_str(table.column(isnad_col)[i].as_py())

            # Fall back to full text if isnad is missing.
            if not isnad_text:
                isnad_text = safe_str(table.column(text_col)[i].as_py())
            if not isnad_text:
                null_isnad_count += 1
                continue

            spans = extract_narrator_mentions(isnad_text, language)
            for span in spans:
                name_raw = span.name
                if language == "ar":
                    name_normalized = normalize_arabic(name_raw)
                else:
                    name_normalized = name_raw.strip()

                rows.append(
                    {
                        "mention_id": str(uuid.uuid4()),
                        "hadith_id": hadith_id,
                        "source_corpus": corpus,
                        "position_in_chain": span.position,
                        "name_raw": name_raw,
                        "name_normalized": name_normalized,
                        "canonical_narrator_id": None,
                        "transmission_method": span.transmission_method,
                        "confidence": None,
                    }
                )

    null_pct = (null_isnad_count / total_hadiths * 100) if total_hadiths else 0.0
    logger.info(
        "extraction_complete",
        corpus=corpus,
        language=language,
        total_hadiths=total_hadiths,
        null_isnad_pct=round(null_pct, 1),
        mentions_extracted=len(rows),
        mentions_per_hadith=round(len(rows) / max(total_hadiths, 1), 2),
    )
    return rows


def _write_name_audit_csv(
    rows: list[dict[str, str | int | None]],
    output_dir: Path,
    sample_size: int = 100,
) -> Path:
    """Export a random sample of name_raw vs name_normalized for manual audit."""
    audit_path = output_dir / "ner_name_audit.csv"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect rows that have both raw and normalized names.
    candidates = [r for r in rows if r.get("name_raw") and r.get("name_normalized")]
    rng = random.Random(42)
    sample = rng.sample(candidates, min(sample_size, len(candidates)))

    with open(audit_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source_corpus", "name_raw", "name_normalized", "is_arabic"])
        for r in sample:
            raw = str(r["name_raw"])
            writer.writerow([r["source_corpus"], raw, r["name_normalized"], is_arabic(raw)])

    logger.info("name_audit_written", path=str(audit_path), rows=len(sample))
    return audit_path


def run(staging_dir: Path, output_dir: Path) -> list[Path]:
    """Extract narrator mentions from parsed isnad chains.

    Reads staging Parquet files and produces resolved narrator mention tables.
    Returns list of output file paths.
    """
    logger.info("ner_run_start", staging_dir=str(staging_dir), output_dir=str(output_dir))

    all_rows: list[dict[str, str | int | None]] = []

    # Step 1: Load Phase 1 pre-extracted mentions (sanadset, lk).
    for corpus, filename in _PHASE1_MENTION_SOURCES.items():
        rows = _load_phase1_mentions(staging_dir, corpus, filename)
        all_rows.extend(rows)

    # Step 2: Extract from Arabic-text sources.
    for corpus in sorted(_ARABIC_SOURCES):
        rows = _extract_from_hadiths(staging_dir, corpus, language="ar")
        all_rows.extend(rows)

    # Step 3: Extract from English-only sources.
    for corpus in sorted(_ENGLISH_SOURCES):
        rows = _extract_from_hadiths(staging_dir, corpus, language="en")
        all_rows.extend(rows)

    # Step 4: Log skipped sources.
    for corpus in sorted(_SKIP_SOURCES):
        logger.info("ner_skip_source", corpus=corpus, reason="no_raw_isnads")

    # Step 5: Per-source metrics summary.
    source_counts: dict[str, int] = {}
    for r in all_rows:
        src = str(r["source_corpus"])
        source_counts[src] = source_counts.get(src, 0) + 1
    for src, count in sorted(source_counts.items()):
        logger.info("ner_source_summary", source_corpus=src, total_mentions=count)
    logger.info("ner_total_mentions", total=len(all_rows))

    # Step 6: Build output table.
    output_paths: list[Path] = []

    if all_rows:
        arrays: dict[str, pa.Array] = {
            "mention_id": pa.array([r["mention_id"] for r in all_rows], type=pa.string()),
            "hadith_id": pa.array([r["hadith_id"] for r in all_rows], type=pa.string()),
            "source_corpus": pa.array([r["source_corpus"] for r in all_rows], type=pa.string()),
            "position_in_chain": pa.array(
                [r["position_in_chain"] for r in all_rows], type=pa.int32()
            ),
            "name_raw": pa.array([r["name_raw"] for r in all_rows], type=pa.string()),
            "name_normalized": pa.array([r["name_normalized"] for r in all_rows], type=pa.string()),
            "canonical_narrator_id": pa.array(
                [r["canonical_narrator_id"] for r in all_rows], type=pa.string()
            ),
            "transmission_method": pa.array(
                [r["transmission_method"] for r in all_rows], type=pa.string()
            ),
            "confidence": pa.array([r["confidence"] for r in all_rows], type=pa.float32()),
        }
        table = pa.table(arrays, schema=NARRATOR_MENTIONS_RESOLVED_SCHEMA)
        resolved_path = output_dir / "narrator_mentions_resolved.parquet"
        write_parquet(table, resolved_path, schema=NARRATOR_MENTIONS_RESOLVED_SCHEMA)
        output_paths.append(resolved_path)
    else:
        logger.warning("ner_no_mentions", msg="No narrator mentions extracted from any source")

    # Step 7: Name audit CSV.
    if all_rows:
        audit_path = _write_name_audit_csv(all_rows, output_dir)
        output_paths.append(audit_path)

    logger.info("ner_run_complete", output_files=[str(p) for p in output_paths])
    return output_paths
