"""Download the Sanadset hadith dataset and narrators dataset from Kaggle.

Datasets:
- ``fahd09/hadith-dataset`` — ~650K hadiths with XML-style SANAD/MATN/NAR tags
- ``fahd09/hadith-narrators`` — narrator biographies

Requires either ``KAGGLE_USERNAME`` + ``KAGGLE_KEY`` in settings/.env, or a
valid ``~/.kaggle/kaggle.json`` file.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from src.acquire.base import ensure_dir, write_manifest
from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["download_sanadset"]

_HADITH_DATASET = "fahd09/hadith-dataset"
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
    """Download Sanadset hadith + narrators datasets from Kaggle.

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
        If Kaggle credentials are not available or validation fails.
    """
    if not _kaggle_credentials_available():
        msg = (
            "Kaggle credentials not found. Set KAGGLE_USERNAME + KAGGLE_KEY in .env "
            "or create ~/.kaggle/kaggle.json"
        )
        raise RuntimeError(msg)

    settings = get_settings()
    if dest is None:
        dest = settings.data_raw_dir / "sanadset"
    dest = ensure_dir(dest)

    # Download hadith dataset (idempotent: skip if CSV files already present)
    hadith_csvs = list(dest.glob("*.csv"))
    if hadith_csvs:
        logger.info("download_skipped", dataset=_HADITH_DATASET, reason="csv_files_exist")
    else:
        _run_kaggle_download(_HADITH_DATASET, dest)

    # Download narrators dataset to subdirectory
    narrators_dir = ensure_dir(dest / "narrators")
    narrators_csvs = list(narrators_dir.glob("*.csv"))
    if narrators_csvs:
        logger.info("download_skipped", dataset=_NARRATORS_DATASET, reason="csv_files_exist")
    else:
        _run_kaggle_download(_NARRATORS_DATASET, narrators_dir)

    # Validate: CSV files exist
    hadith_csvs = list(dest.glob("*.csv"))
    if not hadith_csvs:
        msg = f"No CSV files found in {dest} after downloading {_HADITH_DATASET}"
        raise RuntimeError(msg)

    narrators_csvs = list(narrators_dir.glob("*.csv"))
    if not narrators_csvs:
        msg = f"No CSV files found in {narrators_dir} after downloading {_NARRATORS_DATASET}"
        raise RuntimeError(msg)

    # Validate: minimum row count for hadith data
    total_rows = _count_csv_rows(dest)
    if total_rows < _MIN_EXPECTED_ROWS:
        logger.warning(
            "low_row_count",
            total_rows=total_rows,
            expected_min=_MIN_EXPECTED_ROWS,
        )

    logger.info(
        "sanadset_download_complete",
        hadith_csvs=len(hadith_csvs),
        narrators_csvs=len(narrators_csvs),
        total_rows=total_rows,
    )

    all_files = [*hadith_csvs, *narrators_csvs]
    write_manifest(dest, all_files)
    return dest
