"""Download small samples from each data source for integration testing.

Usage: python scripts/sample_real_data.py --output data/test_samples/

Creates a small subset (first 100 records or first file) from each
known data source for fast integration test runs. Output directory
is gitignored.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

DATA_RAW_DEFAULT = Path("data/raw")
OUTPUT_DEFAULT = Path("data/test_samples")
SAMPLE_ROWS = 100


def _sample_csv(src: Path, dst: Path, max_rows: int = SAMPLE_ROWS) -> int:
    """Copy up to max_rows from a CSV file, preserving the header."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with (
        open(src, encoding="utf-8", errors="replace") as fin,
        open(dst, "w", encoding="utf-8", newline="") as fout,
    ):
        reader = csv.reader(fin)
        writer = csv.writer(fout)
        for i, row in enumerate(reader):
            writer.writerow(row)
            if i == 0:
                continue  # header
            count += 1
            if count >= max_rows:
                break
    return count


def _sample_json(src: Path, dst: Path, max_items: int = SAMPLE_ROWS) -> int:
    """Copy up to max_items from a JSON lines or JSON array file."""
    import json

    dst.parent.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8", errors="replace")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try JSON lines
        lines = text.strip().splitlines()
        data = [json.loads(line) for line in lines[:max_items] if line.strip()]
        dst.write_text(json.dumps(data[:max_items], ensure_ascii=False, indent=2))
        return min(len(data), max_items)

    if isinstance(data, list):
        sample = data[:max_items]
        dst.write_text(json.dumps(sample, ensure_ascii=False, indent=2))
        return len(sample)

    # Single object — copy as-is
    shutil.copy2(src, dst)
    return 1


def _sample_source(name: str, raw_dir: Path, output_dir: Path) -> int:
    """Sample a single data source. Returns count of rows sampled."""
    src_dir = raw_dir / name
    if not src_dir.exists():
        print(f"  [{name:15s}] SKIP — source dir not found: {src_dir}")
        return 0

    dst_dir = output_dir / name
    total = 0

    csv_files = sorted(src_dir.rglob("*.csv"))
    json_files = sorted(src_dir.rglob("*.json"))

    # Sample first CSV file from each source
    for csv_file in csv_files[:1]:
        rel = csv_file.relative_to(src_dir)
        count = _sample_csv(csv_file, dst_dir / rel)
        total += count
        print(f"  [{name:15s}] CSV  {rel} -> {count} rows")

    # Sample first JSON file from each source
    for json_file in json_files[:1]:
        rel = json_file.relative_to(src_dir)
        count = _sample_json(json_file, dst_dir / rel)
        total += count
        print(f"  [{name:15s}] JSON {rel} -> {count} items")

    if total == 0:
        print(f"  [{name:15s}] SKIP — no CSV/JSON files found")

    return total


def cleanup(output_dir: Path) -> None:
    """Remove all sampled data for a clean state."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
        print(f"Cleaned up: {output_dir}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Sample real data for integration testing")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DEFAULT,
        help="Output directory for samples",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DATA_RAW_DEFAULT,
        help="Raw data directory to sample from",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=SAMPLE_ROWS,
        help="Max rows to sample per source",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing samples before downloading",
    )
    args = parser.parse_args()

    if args.clean:
        cleanup(args.output)

    args.output.mkdir(parents=True, exist_ok=True)

    sources = ["lk", "sanadset", "thaqalayn", "fawaz", "sunnah", "open_hadith", "muhaddithat"]

    print(f"Sampling from {args.raw_dir} -> {args.output}")
    print(f"Max rows per source: {args.rows}")
    print()

    grand_total = 0
    for name in sources:
        grand_total += _sample_source(name, args.raw_dir, args.output)

    print(f"\nTotal sampled: {grand_total} records across {len(sources)} sources")

    if grand_total == 0:
        print(
            "\nNo raw data found. Run `make acquire` first to download source data.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
