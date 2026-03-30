"""Data quality validation framework for staging Parquet files.

Provides per-source validation with schema conformance, null rate analysis,
duplicate detection, Arabic text encoding checks, and drift detection against
expected baselines. Produces structured Pydantic-based JSON reports.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict

from src.parse.schemas import (
    COLLECTION_SCHEMA,
    HADITH_SCHEMA,
    NARRATOR_BIO_SCHEMA,
    NARRATOR_MENTION_SCHEMA,
    NETWORK_EDGE_SCHEMA,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Schema mapping
# ---------------------------------------------------------------------------

EXPECTED_SCHEMAS: dict[str, pa.Schema] = {
    "hadiths_": HADITH_SCHEMA,
    "narrator_mentions_": NARRATOR_MENTION_SCHEMA,
    "narrators_bio_": NARRATOR_BIO_SCHEMA,
    "collections_": COLLECTION_SCHEMA,
    "network_edges_": NETWORK_EDGE_SCHEMA,
}

_ARABIC_RE = re.compile("[\u0600-\u06ff]")

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Strictness(StrEnum):
    """Gate strictness level."""

    STRICT = "strict"
    WARN = "warn"


class CheckStatus(StrEnum):
    """Result status for a single validation check."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


# ---------------------------------------------------------------------------
# Pydantic report models (frozen for immutability per project convention)
# ---------------------------------------------------------------------------


class CheckResult(BaseModel):
    """Result of a single validation check."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: CheckStatus
    message: str
    value: float | int | str | None = None
    threshold: float | int | str | None = None


class DriftResult(BaseModel):
    """Drift detection result comparing current metrics against a baseline."""

    model_config = ConfigDict(frozen=True)

    metric: str
    baseline_value: float | int
    current_value: float | int
    drift_pct: float
    within_tolerance: bool
    tolerance_pct: float


class FileReport(BaseModel):
    """Validation report for a single Parquet file."""

    model_config = ConfigDict(frozen=True)

    file: str
    source: str
    rows: int
    columns: int
    null_percentages: dict[str, float]
    checks: list[CheckResult]
    drift: list[DriftResult]
    passed: bool


class ValidationReport(BaseModel):
    """Top-level validation report for all staging files."""

    model_config = ConfigDict(frozen=True)

    timestamp: str
    staging_dir: str
    strictness: Strictness
    total_files: int
    total_rows: int
    files: list[FileReport]
    passed: bool


# ---------------------------------------------------------------------------
# Default baselines for drift detection
# ---------------------------------------------------------------------------

DEFAULT_BASELINES: dict[str, dict[str, float | int]] = {
    # Baselines calibrated from Wave 3 full pipeline run (2026-03-30)
    "hadiths_sunnah_api": {"row_count": 30000, "arabic_coverage_pct": 90.0},
    "hadiths_open_hadith": {"row_count": 62160, "arabic_coverage_pct": 0.0},
    "hadiths_thaqalayn": {"row_count": 113401, "arabic_coverage_pct": 0.0},
    "hadiths_lk": {"row_count": 34088, "arabic_coverage_pct": 99.0},
    "hadiths_fawaz": {"row_count": 0, "arabic_coverage_pct": 0.0},
    "hadiths_sanadset": {"row_count": 650986, "arabic_coverage_pct": 90.0},
    "hadiths_sunnah_scraped": {"row_count": 10028, "arabic_coverage_pct": 90.0},
    "hadiths_muhaddithat": {"row_count": 0, "arabic_coverage_pct": 0.0},
    "narrator_mentions_sunnah_api": {"row_count": 100000},
    "narrator_mentions_thaqalayn": {"row_count": 405360},
    "narrator_mentions_lk": {"row_count": 86162},
    "narrator_mentions_sanadset": {"row_count": 2789517},
    "narrators_bio_kaggle": {"row_count": 24326},
    "narrators_bio_muhaddithat": {"row_count": 113},
    "collections_sunnah_api": {"row_count": 15},
    "collections_sunnah_scraped": {"row_count": 5},
    "collections_thaqalayn": {"row_count": 64},
    "collections_lk": {"row_count": 6},
    "collections_fawaz": {"row_count": 0},
    "network_edges_muhaddithat": {"row_count": 330},
}

DEFAULT_DRIFT_TOLERANCE_PCT = 30.0

# Null-rate thresholds: columns that should never be null
REQUIRED_COLUMNS: dict[str, set[str]] = {
    "hadiths_": {"source_id", "source_corpus", "collection_name", "sect"},
    "narrator_mentions_": {
        "mention_id",
        "source_hadith_id",
        "source_corpus",
        "position_in_chain",
    },
    "narrators_bio_": {"bio_id", "source"},
    "collections_": {"collection_id", "name_en", "sect", "source_corpus"},
    "network_edges_": {"from_narrator_name", "to_narrator_name", "source"},
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


def _extract_source(filename: str) -> str:
    """Extract source name from filename, e.g. 'hadiths_sunnah_api.parquet' -> 'sunnah_api'."""
    stem = Path(filename).stem
    for prefix in EXPECTED_SCHEMAS:
        if stem.startswith(prefix):
            return stem[len(prefix) :]
    return stem


def _baseline_key(filename: str) -> str:
    """Build a key for baseline lookup from filename."""
    return Path(filename).stem


# ---------------------------------------------------------------------------
# Per-file validation
# ---------------------------------------------------------------------------


def _validate_file(
    pf_path: Path,
    strictness: Strictness,
    baselines: dict[str, dict[str, float | int]],
    drift_tolerance_pct: float,
) -> FileReport:
    """Run all validation checks on a single Parquet file."""
    table = pq.read_table(pf_path)
    filename = pf_path.name
    source = _extract_source(filename)
    num_rows = len(table)
    num_cols = len(table.column_names)
    null_pcts = _null_percentages(table)

    checks: list[CheckResult] = []
    drift_results: list[DriftResult] = []

    # -- Row count check --
    checks.append(
        CheckResult(
            name="row_count",
            status=CheckStatus.PASS if num_rows > 0 else CheckStatus.FAIL,
            message=f"{num_rows} rows" if num_rows > 0 else "File is empty",
            value=num_rows,
        )
    )

    # -- Schema conformance --
    match = _match_schema(filename)
    if match is not None:
        _prefix, expected = match
        issues = _check_schema_conformance(table.schema, expected)
        if issues:
            checks.append(
                CheckResult(
                    name="schema_conformance",
                    status=CheckStatus.FAIL,
                    message="; ".join(issues),
                )
            )
        else:
            checks.append(
                CheckResult(
                    name="schema_conformance",
                    status=CheckStatus.PASS,
                    message="Schema matches expected",
                )
            )
    else:
        checks.append(
            CheckResult(
                name="schema_conformance",
                status=CheckStatus.WARN,
                message="No matching expected schema found",
            )
        )

    # -- Required column null checks --
    for prefix, required_cols in REQUIRED_COLUMNS.items():
        if filename.startswith(prefix):
            for col in required_cols:
                if col in table.column_names:
                    pct = null_pcts.get(col, 0.0)
                    checks.append(
                        CheckResult(
                            name=f"null_check_{col}",
                            status=CheckStatus.PASS if pct == 0.0 else CheckStatus.FAIL,
                            message=f"{col} null rate: {pct}%",
                            value=pct,
                            threshold=0.0,
                        )
                    )
            break

    # -- Duplicate detection --
    id_col = _get_id_column(filename)
    if id_col and id_col in table.column_names and num_rows > 0:
        id_array = table.column(id_col)
        total = len(id_array)
        unique = pc.count(pc.unique(id_array)).as_py()
        dupes = total - unique
        dupe_pct = round(100.0 * dupes / total, 2) if total > 0 else 0.0
        checks.append(
            CheckResult(
                name="duplicate_ids",
                status=CheckStatus.PASS if dupes == 0 else CheckStatus.WARN,
                message=f"{dupes} duplicate {id_col} values ({dupe_pct}%)",
                value=dupes,
            )
        )

    # -- Arabic text encoding --
    if num_rows > 0:
        for ar_col in ("name_ar", "matn_ar"):
            if ar_col in table.column_names:
                col = table.column(ar_col)
                non_null = col.drop_null()
                non_null_count = len(non_null)
                if non_null_count > 0:
                    has_arabic = pc.sum(
                        pc.match_substring_regex(non_null, "[\u0600-\u06ff]")
                    ).as_py()
                    ar_pct = round(100.0 * has_arabic / non_null_count, 2)
                    checks.append(
                        CheckResult(
                            name=f"arabic_encoding_{ar_col}",
                            status=CheckStatus.PASS if ar_pct > 50.0 else CheckStatus.WARN,
                            message=f"{ar_pct}% of non-null {ar_col} contain Arabic chars",
                            value=ar_pct,
                            threshold=50.0,
                        )
                    )

    # -- Hadith-specific checks --
    if filename.startswith("hadiths_") and num_rows > 0:
        checks.extend(_hadith_checks(table, num_rows))

    # -- Drift detection --
    bkey = _baseline_key(filename)
    if bkey in baselines:
        baseline = baselines[bkey]
        current_metrics = _current_metrics(table, filename, num_rows)
        for metric, baseline_val in baseline.items():
            if metric in current_metrics:
                current_val = current_metrics[metric]
                if baseline_val != 0:
                    drift_pct = round(
                        100.0 * abs(current_val - baseline_val) / abs(baseline_val), 2
                    )
                else:
                    drift_pct = 0.0 if current_val == 0 else 100.0
                within = drift_pct <= drift_tolerance_pct
                drift_results.append(
                    DriftResult(
                        metric=metric,
                        baseline_value=baseline_val,
                        current_value=current_val,
                        drift_pct=drift_pct,
                        within_tolerance=within,
                        tolerance_pct=drift_tolerance_pct,
                    )
                )

    # Determine pass/fail
    has_failure = any(c.status == CheckStatus.FAIL for c in checks)
    drift_failure = any(not d.within_tolerance for d in drift_results)

    if strictness == Strictness.STRICT:
        passed = not has_failure and not drift_failure
    else:
        passed = not has_failure

    return FileReport(
        file=filename,
        source=source,
        rows=num_rows,
        columns=num_cols,
        null_percentages=null_pcts,
        checks=checks,
        drift=drift_results,
        passed=passed,
    )


def _get_id_column(filename: str) -> str | None:
    """Return the primary ID column for a file type."""
    if filename.startswith("hadiths_"):
        return "source_id"
    if filename.startswith("narrator_mentions_"):
        return "mention_id"
    if filename.startswith("narrators_bio_"):
        return "bio_id"
    if filename.startswith("collections_"):
        return "collection_id"
    return None


def _hadith_checks(table: pa.Table, num_rows: int) -> list[CheckResult]:
    """Run hadith-specific validation checks."""
    checks: list[CheckResult] = []

    # Empty matn_ar
    if "matn_ar" in table.column_names:
        col = table.column("matn_ar")
        null_count = col.null_count
        stripped = pc.utf8_trim(col.drop_null(), " \t\n\r")
        blank_count = pc.sum(pc.equal(stripped, "")).as_py() or 0
        empty = null_count + blank_count
        empty_pct = round(100.0 * empty / num_rows, 2)
        checks.append(
            CheckResult(
                name="empty_matn_ar",
                status=CheckStatus.PASS if empty_pct < 50.0 else CheckStatus.WARN,
                message=f"{empty} empty matn_ar ({empty_pct}%)",
                value=empty,
            )
        )

    # Empty matn_en
    if "matn_en" in table.column_names:
        col = table.column("matn_en")
        null_count = col.null_count
        stripped = pc.utf8_trim(col.drop_null(), " \t\n\r")
        blank_count = pc.sum(pc.equal(stripped, "")).as_py() or 0
        empty = null_count + blank_count
        empty_pct = round(100.0 * empty / num_rows, 2)
        checks.append(
            CheckResult(
                name="empty_matn_en",
                status=CheckStatus.PASS if empty_pct < 50.0 else CheckStatus.WARN,
                message=f"{empty} empty matn_en ({empty_pct}%)",
                value=empty,
            )
        )

    # Book/chapter coverage
    for col_name, label in [("book_number", "book"), ("chapter_number", "chapter")]:
        if col_name in table.column_names:
            filled = num_rows - table.column(col_name).null_count
            pct = round(100.0 * filled / num_rows, 2)
            checks.append(
                CheckResult(
                    name=f"{label}_coverage",
                    status=CheckStatus.PASS,
                    message=f"{label} coverage: {pct}%",
                    value=pct,
                )
            )

    return checks


def _current_metrics(table: pa.Table, filename: str, num_rows: int) -> dict[str, float | int]:
    """Extract metrics from current data for drift comparison."""
    metrics: dict[str, float | int] = {"row_count": num_rows}
    if filename.startswith("hadiths_") and "matn_ar" in table.column_names and num_rows > 0:
        col = table.column("matn_ar")
        non_null = col.drop_null()
        if len(non_null) > 0:
            has_arabic = pc.sum(pc.match_substring_regex(non_null, "[\u0600-\u06ff]")).as_py()
            metrics["arabic_coverage_pct"] = round(100.0 * has_arabic / num_rows, 2)
    return metrics


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_staging(
    staging_dir: Path,
    *,
    strictness: Strictness = Strictness.WARN,
    baselines: dict[str, dict[str, float | int]] | None = None,
    drift_tolerance_pct: float = DEFAULT_DRIFT_TOLERANCE_PCT,
    output_json: Path | None = None,
) -> ValidationReport:
    """Validate all Parquet files in staging_dir.

    Args:
        staging_dir: Directory containing staging Parquet files.
        strictness: STRICT halts on any failure; WARN logs failures but passes.
        baselines: Per-source expected metrics for drift detection.
            Defaults to DEFAULT_BASELINES.
        drift_tolerance_pct: Maximum allowed drift percentage from baseline.
        output_json: If provided, write JSON report to this path.

    Returns:
        A ValidationReport with per-file results.
    """
    if baselines is None:
        baselines = DEFAULT_BASELINES

    parquet_files = sorted(staging_dir.glob("*.parquet"))
    if not parquet_files:
        logger.warning("no_parquet_files", staging_dir=str(staging_dir))
        report = ValidationReport(
            timestamp=datetime.now(UTC).isoformat(),
            staging_dir=str(staging_dir),
            strictness=strictness,
            total_files=0,
            total_rows=0,
            files=[],
            passed=True,
        )
        if output_json:
            _write_json(report, output_json)
        return report

    file_reports: list[FileReport] = []
    for pf_path in parquet_files:
        fr = _validate_file(pf_path, strictness, baselines, drift_tolerance_pct)
        file_reports.append(fr)
        logger.info(
            "file_validated",
            file=fr.file,
            rows=fr.rows,
            passed=fr.passed,
            checks_failed=sum(1 for c in fr.checks if c.status == CheckStatus.FAIL),
        )

    all_passed = all(fr.passed for fr in file_reports)

    report = ValidationReport(
        timestamp=datetime.now(UTC).isoformat(),
        staging_dir=str(staging_dir),
        strictness=strictness,
        total_files=len(file_reports),
        total_rows=sum(fr.rows for fr in file_reports),
        files=file_reports,
        passed=all_passed,
    )

    _print_report(report)

    if output_json:
        _write_json(report, output_json)

    return report


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _write_json(report: ValidationReport, path: Path) -> None:
    """Write validation report as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.model_dump(mode="json"), indent=2))
    logger.info("report_written", path=str(path))


def _print_report(report: ValidationReport) -> None:
    """Print a formatted validation report to stdout."""
    print("=" * 70)
    print("STAGING DATA VALIDATION REPORT")
    print(f"  Timestamp:  {report.timestamp}")
    print(f"  Strictness: {report.strictness.value}")
    print("=" * 70)
    print(f"Total files: {report.total_files}")
    print(f"Total rows:  {report.total_rows}")
    print(f"Overall:     {'PASSED' if report.passed else 'FAILED'}")
    print()

    for fr in report.files:
        status = "PASS" if fr.passed else "FAIL"
        print("-" * 70)
        print(f"[{status}] {fr.file}  (source: {fr.source})")
        print(f"  Rows: {fr.rows:,}  |  Columns: {fr.columns}")

        # Checks
        failed = [c for c in fr.checks if c.status in (CheckStatus.FAIL, CheckStatus.WARN)]
        passed = [c for c in fr.checks if c.status == CheckStatus.PASS]
        if failed:
            print("  Issues:")
            for c in failed:
                print(f"    [{c.status.value.upper()}] {c.name}: {c.message}")
        print(f"  Checks: {len(passed)} passed, {len(failed)} issues")

        # Drift
        if fr.drift:
            print("  Drift:")
            for d in fr.drift:
                marker = "OK" if d.within_tolerance else "DRIFT"
                print(
                    f"    [{marker}] {d.metric}: "
                    f"baseline={d.baseline_value}, current={d.current_value}, "
                    f"drift={d.drift_pct}% (tolerance={d.tolerance_pct}%)"
                )

        # Null rates (only show columns with nulls)
        cols_with_nulls = {k: v for k, v in fr.null_percentages.items() if v > 0}
        if cols_with_nulls:
            print("  Null % (columns with nulls):")
            for col, pct in sorted(cols_with_nulls.items()):
                print(f"    {col}: {pct}%")

        print()

    print("=" * 70)
