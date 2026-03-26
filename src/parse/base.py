"""Shared parsing utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq

from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "write_parquet",
    "read_csv_robust",
    "generate_source_id",
    "safe_int",
    "safe_str",
    "validate_enum_fields",
]


def write_parquet(table: pa.Table, path: Path, schema: pa.Schema | None = None) -> Path:
    """Write PyArrow Table to Parquet with Snappy compression.

    Validate against schema if provided. Create parent dirs. Log stats.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if schema is not None:
        table = table.cast(schema)
    pq.write_table(table, path, compression="snappy")
    size_mb = path.stat().st_size / (1024 * 1024)
    logger.info("wrote_parquet", path=str(path), rows=table.num_rows, size_mb=round(size_mb, 2))
    return path


def read_csv_robust(path: Path, encoding: str = "utf-8", **kwargs: Any) -> tuple[pa.Table, str]:
    """Read CSV with fallback encoding chain. Returns (table, encoding_used).

    Try: specified -> utf-8-sig -> latin-1.
    """
    encodings = [encoding]
    if encoding != "utf-8-sig":
        encodings.append("utf-8-sig")
    if "latin-1" not in encodings:
        encodings.append("latin-1")

    for enc in encodings:
        try:
            read_options = pcsv.ReadOptions(encoding=enc)
            table = pcsv.read_csv(str(path), read_options=read_options, **kwargs)
            logger.info("csv_read", path=str(path), encoding=enc, rows=table.num_rows)
            return table, enc
        except Exception:  # noqa: BLE001
            logger.warning("csv_encoding_failed", path=str(path), encoding=enc)
            continue

    msg = f"Failed to read CSV {path} with any encoding: {encodings}"
    raise ValueError(msg)


def generate_source_id(corpus: str, collection: str, *parts: int | str) -> str:
    """Generate deterministic source_id.

    Example: ``generate_source_id("lk", "bukhari", 1, 1)`` -> ``"lk:bukhari:1:1"``
    """
    segments = [corpus, collection, *[str(p) for p in parts]]
    return ":".join(segments)


def safe_int(value: Any) -> int | None:
    """Safely convert to int. Return None on failure."""
    if value is None:
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):  # fmt: skip
        return None


def safe_str(value: Any) -> str | None:
    """Convert to stripped string. Return None if empty/NaN/None."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() in ("nan", "none"):
        return None
    return s


def validate_enum_fields(
    table: pa.Table,
    field_name: str,
    allowed_values: set[str],
) -> list[str]:
    """Validate string column values against allowed set.

    Returns list of invalid values found. Logs warnings.
    """
    column = table.column(field_name)
    unique_values: list[str | None] = column.unique().to_pylist()
    invalid = [v for v in unique_values if v is not None and v not in allowed_values]
    if invalid:
        logger.warning(
            "invalid_enum_values",
            field=field_name,
            invalid_values=invalid,
            allowed=sorted(allowed_values),
        )
    return invalid
