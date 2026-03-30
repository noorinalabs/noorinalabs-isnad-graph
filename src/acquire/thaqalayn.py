"""Acquire hadith data from the Thaqalayn GitHub repository.

Fetches Shia hadith collections by cloning the MohammedArab1/ThaqalaynAPI
GitHub repository. The Thaqalayn REST API v2 was removed circa early 2026
when the website was rebuilt with Next.js — the GitHub repo is now the
primary acquisition method.
"""

from __future__ import annotations

from pathlib import Path

from src.acquire.base import clone_repo, ensure_dir, write_manifest
from src.utils.logging import get_logger

logger = get_logger(__name__)

THAQALAYN_GITHUB_URL = "https://github.com/MohammedArab1/ThaqalaynAPI.git"
MIN_EXPECTED_BOOKS = 15


def _download_via_github(dest: Path) -> list[Path]:
    """Clone the ThaqalaynAPI repo. Returns JSON files found."""
    github_dest = dest / "github_clone"
    clone_repo(THAQALAYN_GITHUB_URL, github_dest)
    json_files = list(github_dest.rglob("*.json"))
    logger.info("thaqalayn_github_clone", file_count=len(json_files))
    return json_files


def run(raw_dir: Path) -> Path:
    """Download Thaqalayn data via GitHub clone."""
    dest = ensure_dir(raw_dir / "thaqalayn")

    # Check for idempotent skip: already have enough book JSONs
    existing_books = list(dest.glob("book_*.json"))
    github_clone = dest / "github_clone"
    github_jsons = list(github_clone.rglob("*.json")) if github_clone.exists() else []
    if len(existing_books) >= MIN_EXPECTED_BOOKS or len(github_jsons) >= MIN_EXPECTED_BOOKS:
        all_files = existing_books or github_jsons
        logger.info(
            "thaqalayn_skipped",
            reason="already_acquired",
            file_count=len(all_files),
        )
        write_manifest(dest, all_files)
        return dest

    saved = _download_via_github(dest)

    json_files = [f for f in saved if f.suffix == ".json"]
    if len(json_files) < MIN_EXPECTED_BOOKS:
        msg = (
            f"Expected >= {MIN_EXPECTED_BOOKS} JSON files from GitHub clone, "
            f"found {len(json_files)}"
        )
        raise AssertionError(msg)

    write_manifest(dest, json_files)
    logger.info("thaqalayn_acquired", total_files=len(json_files))
    return dest
