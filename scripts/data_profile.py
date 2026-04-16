"""Data profiling script for staging Parquet files.

Reads all staging Parquet files, reports row counts, column types, null rates,
unique value counts for key columns, and checks schema conformance against
expected PyArrow schemas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

from src.parse.schemas import (
    COLLECTION_SCHEMA,
    HADITH_SCHEMA,
    NARRATOR_BIO_SCHEMA,
    NARRATOR_MENTION_SCHEMA,
    NETWORK_EDGE_SCHEMA,
)

EXPECTED_SCHEMAS: dict[str, object] = {
    "hadith": HADITH_SCHEMA,
    "narrator_mention": NARRATOR_MENTION_SCHEMA,
    "narrator_bio": NARRATOR_BIO_SCHEMA,
    "collection": COLLECTION_SCHEMA,
    "network_edge": NETWORK_EDGE_SCHEMA,
}


def _match_schema(filename: str) -> object | None:
    """Match a Parquet filename to its expected schema by keyword."""
    name_lower = filename.lower()
    for key, schema in EXPECTED_SCHEMAS.items():
        if key in name_lower:
            return schema
    return None


def _check_schema_conformance(actual_names: list[str], expected_schema: object) -> list[str]:
    """Compare actual column names against expected schema fields."""
    import pyarrow as pa

    if not isinstance(expected_schema, pa.Schema):
        return []

    expected_names = set(expected_schema.names)
    actual_set = set(actual_names)
    issues: list[str] = []

    missing = expected_names - actual_set
    extra = actual_set - expected_names

    if missing:
        issues.append(f"Missing columns: {sorted(missing)}")
    if extra:
        issues.append(f"Extra columns: {sorted(extra)}")

    return issues


def _profile_file(filepath: Path) -> dict:
    """Profile a single Parquet file."""
    table = pq.read_table(filepath)
    num_rows = table.num_rows
    schema = table.schema

    columns: dict[str, dict] = {}
    for i, field in enumerate(schema):
        col = table.column(i)
        null_count = col.null_count
        null_rate = null_count / num_rows if num_rows > 0 else 0.0
        unique_count = col.to_pandas().nunique()

        columns[field.name] = {
            "type": str(field.type),
            "nullable": field.nullable,
            "null_count": null_count,
            "null_rate": round(null_rate, 4),
            "unique_values": unique_count,
        }

    result: dict = {
        "file": filepath.name,
        "path": str(filepath),
        "rows": num_rows,
        "columns": columns,
    }

    expected = _match_schema(filepath.name)
    if expected is not None:
        issues = _check_schema_conformance(list(columns.keys()), expected)
        result["schema_conformance"] = "PASS" if not issues else "FAIL"
        if issues:
            result["schema_issues"] = issues
    else:
        result["schema_conformance"] = "UNKNOWN (no matching schema)"

    return result


def profile_staging(staging_dir: Path) -> dict:
    """Profile all Parquet files in the staging directory."""
    parquet_files = sorted(staging_dir.glob("**/*.parquet"))

    if not parquet_files:
        return {
            "staging_dir": str(staging_dir),
            "total_files": 0,
            "files": [],
            "summary": "No Parquet files found in staging directory.",
        }

    file_profiles = []
    total_rows = 0

    for pf in parquet_files:
        profile = _profile_file(pf)
        file_profiles.append(profile)
        total_rows += profile["rows"]

    return {
        "staging_dir": str(staging_dir),
        "total_files": len(file_profiles),
        "total_rows": total_rows,
        "files": file_profiles,
    }


def main() -> None:
    """Run data profiling and print report."""
    from src.config import get_settings

    settings = get_settings()
    staging_dir = Path(settings.data_staging_dir)

    report = profile_staging(staging_dir)
    report_json = json.dumps(report, indent=2)

    print(report_json)

    # Optionally write to file
    output_path = staging_dir / "profile_report.json"
    if staging_dir.exists():
        output_path.write_text(report_json)
        print(f"\nReport written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
