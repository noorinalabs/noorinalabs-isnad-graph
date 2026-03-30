#!/usr/bin/env python3
"""Generate a manifest of Parquet files for incremental pipeline diffing.

Walks data/staging/ and data/curated/, computes MD5 hash, row count, and file
size for each .parquet file, and writes the result to data/.manifest.json.

Usage:
    python scripts/generate_manifest.py [--data-dir DATA_DIR] [--output OUTPUT]
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq


def md5_file(path: Path, chunk_size: int = 8192) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest(data_dir: Path) -> dict[str, dict]:
    manifest: dict[str, dict] = {}
    for subdir in ("staging", "curated"):
        d = data_dir / subdir
        if not d.exists():
            continue
        for p in sorted(d.glob("*.parquet")):
            key = f"{subdir}/{p.name}"
            rows = pq.read_metadata(p).num_rows
            manifest[key] = {
                "md5": md5_file(p),
                "rows": rows,
                "size_bytes": p.stat().st_size,
            }
    return manifest


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
        help="Root data directory containing staging/ and curated/",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: <data-dir>/.manifest.json)",
    )
    args = parser.parse_args()

    output = args.output or args.data_dir / ".manifest.json"
    manifest = generate_manifest(args.data_dir)

    if not manifest:
        print("No parquet files found — nothing to write.", file=sys.stderr)
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(manifest)} entries to {output}")


if __name__ == "__main__":
    main()
