"""Phase 1: Downloaders for hadith data sources.

This package contains source-specific downloaders that fetch raw data from
CSV files, JSON APIs, Kaggle datasets, and Git repositories into ``data/raw/``.
Shared HTTP/download/clone utilities live in ``base.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.acquire import fawaz, lk_corpus, muhaddithat, open_hadith, sunnah_api, thaqalayn
from src.acquire.sanadset import download_sanadset
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from types import ModuleType

logger = get_logger(__name__)

# Each entry is (name, callable(raw_dir) -> Path | None).
# Most modules expose ``run(raw_dir)``; sanadset uses ``download_sanadset``.
SOURCES: list[tuple[str, ModuleType]] = [
    ("lk", lk_corpus),
    ("sanadset", None),  # type: ignore[list-item]  # handled separately
    ("thaqalayn", thaqalayn),
    ("fawaz", fawaz),
    ("sunnah", sunnah_api),
    ("open_hadith", open_hadith),
    ("muhaddithat", muhaddithat),
]


def _acquire_one(name: str, module: ModuleType | None, raw_dir: Path) -> Path | None:
    """Run a single downloader, returning its output path."""
    if name == "sanadset":
        return download_sanadset(raw_dir / "sanadset")
    assert module is not None
    return module.run(raw_dir)  # type: ignore[no-any-return]


def run_all(raw_dir: Path) -> dict[str, Path | None]:
    """Run all downloaders. Continue on failure. Return dict of source -> path."""
    results: dict[str, Path | None] = {}
    for name, module in SOURCES:
        try:
            logger.info("acquiring", source=name)
            path = _acquire_one(name, module, raw_dir)
            results[name] = path
            logger.info("acquired", source=name, path=str(path) if path else "skipped")
        except Exception as exc:  # noqa: BLE001
            logger.error("acquire_failed", source=name, error=str(exc))
            results[name] = None

    # Summary table
    print("\n=== Acquisition Summary ===")
    for name, path in results.items():
        status = "ok" if path else "FAIL"
        if path and path.exists():
            files = [f for f in path.rglob("*") if f.is_file()]
            file_count = len(files)
            total_size = sum(f.stat().st_size for f in files)
            size_mb = total_size / 1024 / 1024
            print(f"  [{status:4s}] {name:15s}  {file_count:>4d} files  {size_mb:>8.1f} MB")
        else:
            print(f"  [{status:4s}] {name:15s}  --")

    return results
