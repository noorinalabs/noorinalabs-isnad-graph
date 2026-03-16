"""Staging data validation and reporting."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.parse.schemas import (
    COLLECTION_SCHEMA,
    HADITH_SCHEMA,
    NARRATOR_BIO_SCHEMA,
    NARRATOR_MENTION_SCHEMA,
    NETWORK_EDGE_SCHEMA,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

EXPECTED_SCHEMAS: dict[str, pa.Schema] = {
    "hadiths_": HADITH_SCHEMA,
    "narrator_mentions_": NARRATOR_MENTION_SCHEMA,
    "narrators_bio_": NARRATOR_BIO_SCHEMA,
    "collections_": COLLECTION_SCHEMA,
    "network_edges_": NETWORK_EDGE_SCHEMA,
}

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def _has_arabic(text: str) -> bool:
    """Return True if text contains at least one Arabic character."""
    return bool(_ARABIC_RE.search(text))


def _null_percentages(table: pa.Table) -> dict[str, float]:
    """Compute null percentage per column for a PyArrow table."""
    result: dict[str, float] = {}
    num_rows = len(table)
    if num_rows == 0:
        return {col: 0.0 for col in table.column_names}
    for col_name in table.column_names:
        col = table.column(col_name)
        null_count = col.null_count
        result[col_name] = round(100.0 * null_count / num_rows, 2)
    return result


def _match_schema(filename: str) -> tuple[str, pa.Schema] | None:
    """Match a filename against expected schema prefixes."""
    for prefix, schema in EXPECTED_SCHEMAS.items():
        if filename.startswith(prefix):
            return prefix, schema
    return None


def _check_schema_conformance(table_schema: pa.Schema, expected_schema: pa.Schema) -> list[str]:
    """Compare table schema against expected. Return list of issues."""
    issues: list[str] = []
    expected_names = {f.name for f in expected_schema}
    actual_names = {f.name for f in table_schema}

    missing = expected_names - actual_names
    extra = actual_names - expected_names

    if missing:
        issues.append(f"Missing columns: {sorted(missing)}")
    if extra:
        issues.append(f"Extra columns: {sorted(extra)}")

    for field in expected_schema:
        if field.name in actual_names:
            actual_field = table_schema.field(field.name)
            if actual_field.type != field.type:
                issues.append(
                    f"Column '{field.name}' type mismatch: "
                    f"expected {field.type}, got {actual_field.type}"
                )
    return issues


def validate_staging(staging_dir: Path) -> dict[str, Any]:
    """Read all Parquet files in staging_dir and validate them.

    For each file:
    - Report row count, column count, null % per column
    - Verify schema matches expected staging schema
    - For hadith files: check duplicate source_ids, empty matn, Arabic/English coverage

    Returns a summary dict with all findings. Also prints a formatted report.
    """
    parquet_files = sorted(staging_dir.glob("*.parquet"))
    if not parquet_files:
        print(f"No Parquet files found in {staging_dir}")
        logger.warning("no_parquet_files", staging_dir=str(staging_dir))
        return {"files": [], "total_files": 0}

    results: list[dict[str, Any]] = []

    for pf_path in parquet_files:
        table = pq.read_table(pf_path)
        filename = pf_path.name
        num_rows = len(table)
        num_cols = len(table.column_names)
        null_pcts = _null_percentages(table)

        file_result: dict[str, Any] = {
            "file": filename,
            "rows": num_rows,
            "columns": num_cols,
            "null_percentages": null_pcts,
            "schema_issues": [],
            "is_hadith": False,
        }

        # Schema conformance
        match = _match_schema(filename)
        if match is not None:
            _prefix, expected = match
            issues = _check_schema_conformance(table.schema, expected)
            file_result["schema_issues"] = issues
        else:
            file_result["schema_issues"] = ["No matching expected schema found"]

        # Hadith-specific checks
        if filename.startswith("hadiths_"):
            file_result["is_hadith"] = True
            hadith_checks: dict[str, Any] = {}

            # Duplicate source_ids
            if "source_id" in table.column_names:
                source_col = table.column("source_id")
                total = len(source_col)
                unique = pc.count(pc.unique(source_col)).as_py()
                dupes = total - unique
                hadith_checks["duplicate_source_ids"] = dupes
            else:
                hadith_checks["duplicate_source_ids"] = None

            # Empty matn fields — count nulls + empty/whitespace-only strings
            empty_matn_ar = 0
            empty_matn_en = 0
            if "matn_ar" in table.column_names:
                col = table.column("matn_ar")
                null_count = col.null_count
                stripped = pc.utf8_trim(col.drop_null(), " \t\n\r")
                blank_count = pc.sum(pc.equal(stripped, "")).as_py()
                empty_matn_ar = null_count + blank_count
            if "matn_en" in table.column_names:
                col = table.column("matn_en")
                null_count = col.null_count
                stripped = pc.utf8_trim(col.drop_null(), " \t\n\r")
                blank_count = pc.sum(pc.equal(stripped, "")).as_py()
                empty_matn_en = null_count + blank_count
            hadith_checks["empty_matn_ar"] = empty_matn_ar
            hadith_checks["empty_matn_en"] = empty_matn_en

            # Arabic vs English coverage
            ar_count = 0
            en_count = 0
            if "matn_ar" in table.column_names:
                col = table.column("matn_ar")
                non_null = col.drop_null()
                ar_count = pc.sum(pc.match_substring_regex(non_null, r"[\u0600-\u06FF]")).as_py()
            if "matn_en" in table.column_names:
                col = table.column("matn_en")
                non_null = col.drop_null()
                stripped = pc.utf8_trim(non_null, " \t\n\r")
                en_count = pc.sum(pc.not_equal(stripped, "")).as_py()
            if num_rows > 0:
                hadith_checks["arabic_coverage_pct"] = round(100.0 * ar_count / num_rows, 2)
                hadith_checks["english_coverage_pct"] = round(100.0 * en_count / num_rows, 2)
            else:
                hadith_checks["arabic_coverage_pct"] = 0.0
                hadith_checks["english_coverage_pct"] = 0.0

            file_result["hadith_checks"] = hadith_checks

        results.append(file_result)

    summary: dict[str, Any] = {
        "total_files": len(results),
        "files": results,
        "total_rows": sum(r["rows"] for r in results),
    }

    # Print formatted report
    _print_report(summary)

    return summary


def _print_report(summary: dict[str, Any]) -> None:
    """Print a formatted validation report to stdout."""
    print("=" * 70)
    print("STAGING DATA VALIDATION REPORT")
    print("=" * 70)
    print(f"Total files: {summary['total_files']}")
    print(f"Total rows:  {summary['total_rows']}")
    print()

    for file_info in summary["files"]:
        print("-" * 70)
        print(f"File: {file_info['file']}")
        print(f"  Rows: {file_info['rows']:,}  |  Columns: {file_info['columns']}")

        # Schema issues
        issues = file_info["schema_issues"]
        if issues:
            print("  Schema issues:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  Schema: OK")

        # Null percentages
        null_pcts = file_info["null_percentages"]
        cols_with_nulls = {k: v for k, v in null_pcts.items() if v > 0}
        if cols_with_nulls:
            print("  Null % (columns with nulls):")
            for col, pct in sorted(cols_with_nulls.items()):
                print(f"    {col}: {pct}%")
        else:
            print("  Null %: no nulls")

        # Hadith-specific
        if file_info["is_hadith"] and "hadith_checks" in file_info:
            hc = file_info["hadith_checks"]
            print("  Hadith checks:")
            if hc.get("duplicate_source_ids") is not None:
                print(f"    Duplicate source_ids: {hc['duplicate_source_ids']}")
            print(f"    Empty matn_ar: {hc['empty_matn_ar']}")
            print(f"    Empty matn_en: {hc['empty_matn_en']}")
            print(f"    Arabic coverage: {hc['arabic_coverage_pct']}%")
            print(f"    English coverage: {hc['english_coverage_pct']}%")

        print()

    print("=" * 70)
