"""Download the Sanadset hadith dataset from Mendeley Data (primary) or Kaggle (fallback).

Datasets:
- Mendeley Data ``5xth87zwb5`` v4 — sanadset.csv (~650K hadiths), books.csv
- Kaggle ``fahd09/hadith-dataset`` — same data (removed/intermittent as of early 2026)
- Kaggle ``fahd09/hadith-narrators`` — narrator biographies (24K+)

The Kaggle datasets (``fahd09/hadith-dataset`` and ``fahd09/hadith-narrators``) were
removed or made private circa early 2026. Mendeley Data hosts the same Sanadset
corpus (DOI: 10.17632/5xth87zwb5.4) with stable public download URLs and is now
the primary acquisition path. Kaggle is retained as a fallback for the narrators
dataset, which is not available on Mendeley.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.acquire.base import download_file, ensure_dir, write_manifest
from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["download_sanadset"]

# Mendeley Data — Sanadset 650K v4 (DOI: 10.17632/5xth87zwb5.4)
_MENDELEY_DATASET_ID = "5xth87zwb5"
_MENDELEY_FILES_API = (
    f"https://data.mendeley.com/api/datasets/{_MENDELEY_DATASET_ID}/files?version=4"
)
_MENDELEY_FILES: dict[str, dict[str, str]] = {
    "sanadset.csv": {
        "id": "fe0857fa-73af-4873-b652-60eb7347b811",
        "sha256": "bbe4fd3d9ef797a78c9ddfdc7d31a9d2185c2f7efa0ecee75c9fc46b6dcfb5b3",
        "url": (
            "https://data.mendeley.com/public-files/datasets/5xth87zwb5/files/"
            "fe0857fa-73af-4873-b652-60eb7347b811/file_downloaded"
        ),
    },
    "books.csv": {
        "id": "a09faa74-5d63-4baf-82cf-6e139dcea579",
        "sha256": "0e6d45ce409e8fb8d9a246f2ed3d773237a1acc779e9f55b0c026efe87757924",
        "url": (
            "https://data.mendeley.com/public-files/datasets/5xth87zwb5/files/"
            "a09faa74-5d63-4baf-82cf-6e139dcea579/file_downloaded"
        ),
    },
}

# Kaggle fallback (narrators only — not available on Mendeley)
_NARRATORS_DATASET = "fahd09/hadith-narrators"
_SUBPROCESS_TIMEOUT = 600
_MIN_EXPECTED_ROWS = 600_000


def _kaggle_credentials_available() -> bool:
    """Check if Kaggle credentials are available from settings or kaggle.json."""
    settings = get_settings()
    if settings.kaggle_username and settings.kaggle_key:
        return True

    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if kaggle_json.exists():
        try:
            creds = json.loads(kaggle_json.read_text())
            return bool(creds.get("username") and creds.get("key"))
        except (json.JSONDecodeError, OSError):  # fmt: skip
            return False

    return False


def _download_mendeley(dest: Path) -> list[Path]:
    """Download Sanadset CSV files from Mendeley Data. Returns saved paths."""
    saved: list[Path] = []
    for filename, meta in _MENDELEY_FILES.items():
        file_path = dest / filename
        logger.info("mendeley_download_start", filename=filename)
        download_file(
            meta["url"],
            file_path,
            expected_sha256=meta["sha256"],
            timeout=600.0,
        )
        saved.append(file_path)
        logger.info("mendeley_download_complete", filename=filename, size=file_path.stat().st_size)
    return saved


def _run_kaggle_download(dataset: str, dest: Path) -> None:
    """Run ``kaggle datasets download`` via subprocess."""
    cmd = [
        "kaggle",
        "datasets",
        "download",
        "-d",
        dataset,
        "-p",
        str(dest),
        "--unzip",
    ]
    logger.info("kaggle_download_start", dataset=dataset, dest=str(dest))
    try:
        subprocess.run(  # noqa: S603
            cmd,
            timeout=_SUBPROCESS_TIMEOUT,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("kaggle_download_complete", dataset=dataset)
    except subprocess.TimeoutExpired:
        logger.error("kaggle_download_timeout", dataset=dataset, timeout=_SUBPROCESS_TIMEOUT)
        raise
    except subprocess.CalledProcessError as e:
        logger.error("kaggle_download_failed", dataset=dataset, stderr=e.stderr)
        raise


def _count_csv_rows(directory: Path) -> int:
    """Count total data rows across all CSV files in directory (excluding headers)."""
    total = 0
    for csv_file in directory.glob("*.csv"):
        with open(csv_file, encoding="utf-8", errors="replace") as f:
            total += sum(1 for _ in f) - 1  # subtract header
    return total


def download_sanadset(dest: Path | None = None) -> Path:
    """Download Sanadset hadith + narrators datasets.

    Primary source is Mendeley Data (public, no credentials required).
    Narrator biographies are downloaded from Kaggle if credentials are available.

    Parameters
    ----------
    dest
        Destination directory. Defaults to ``{data_raw_dir}/sanadset/``.

    Returns
    -------
    Path
        The destination directory containing downloaded files.

    Raises
    ------
    RuntimeError
        If Mendeley download fails and no fallback succeeds.
    """
    settings = get_settings()
    if dest is None:
        dest = settings.data_raw_dir / "sanadset"
    dest = ensure_dir(dest)

    # Step 1: Download hadith data from Mendeley (primary source)
    hadith_csvs = list(dest.glob("*.csv"))
    if hadith_csvs:
        logger.info("download_skipped", source="mendeley", reason="csv_files_exist")
    else:
        _download_mendeley(dest)

    # Step 2: Download narrators from Kaggle (if credentials available)
    narrators_dir = ensure_dir(dest / "narrators")
    narrators_csvs = list(narrators_dir.glob("*.csv"))
    if narrators_csvs:
        logger.info("download_skipped", dataset=_NARRATORS_DATASET, reason="csv_files_exist")
    elif _kaggle_credentials_available():
        try:
            _run_kaggle_download(_NARRATORS_DATASET, narrators_dir)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            logger.warning(
                "narrators_download_failed",
                dataset=_NARRATORS_DATASET,
                note="Kaggle dataset may be unavailable; narrator biographies will be missing",
            )
    else:
        logger.warning(
            "narrators_skipped",
            reason="no_kaggle_credentials",
            note="Narrator biographies require Kaggle credentials; skipping",
        )

    # Validate: hadith CSV files exist
    hadith_csvs = list(dest.glob("*.csv"))
    if not hadith_csvs:
        msg = f"No CSV files found in {dest} after Mendeley download"
        raise RuntimeError(msg)

    # Validate: minimum row count for hadith data
    total_rows = _count_csv_rows(dest)
    if total_rows < _MIN_EXPECTED_ROWS:
        logger.warning(
            "low_row_count",
            total_rows=total_rows,
            expected_min=_MIN_EXPECTED_ROWS,
        )

    narrators_csvs = list(narrators_dir.glob("*.csv"))

    logger.info(
        "sanadset_download_complete",
        hadith_csvs=len(hadith_csvs),
        narrators_csvs=len(narrators_csvs),
        total_rows=total_rows,
    )

    all_files = [*hadith_csvs, *narrators_csvs]
    write_manifest(dest, all_files)
    return dest
