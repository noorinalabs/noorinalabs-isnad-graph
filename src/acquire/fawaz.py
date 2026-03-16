"""Acquire hadith editions from the Fawaz Ahmed Hadith API CDN.

Downloads English-language edition JSON files and grading metadata (info.json)
from the jsdelivr CDN mirror of fawazahmed0/hadith-api.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from src.acquire.base import (
    DEFAULT_USER_AGENT,
    download_file,
    ensure_dir,
    fetch_json,
    write_manifest,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

EDITIONS_URL = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions.json"
INFO_URL = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/info.json"
EDITION_URL_TEMPLATE = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/{key}.json"
MIN_EXPECTED_EDITIONS = 10


def _english_edition_keys(editions: dict[str, Any] | list[Any]) -> list[str]:
    """Return edition keys that start with ``eng-``."""
    if isinstance(editions, dict):
        return sorted(k for k in editions if k.startswith("eng-"))
    return []


def run(raw_dir: Path) -> Path:
    """Download Fawaz CDN editions (English) and info.json.

    Idempotent — existing files are skipped.
    """
    dest = ensure_dir(raw_dir / "fawaz")

    # 1. Idempotency check — skip network requests if edition files already present
    existing_editions = list(dest.glob("eng-*.json"))
    if len(existing_editions) >= MIN_EXPECTED_EDITIONS:
        logger.info("fawaz_already_acquired", edition_count=len(existing_editions))
        write_manifest(dest, existing_editions)
        return dest

    # 2. Download editions.json (small catalog file)
    editions_path = dest / "editions.json"
    editions_data = fetch_json(EDITIONS_URL)
    if not editions_path.exists() or editions_path.stat().st_size == 0:
        with open(editions_path, "w") as f:
            json.dump(editions_data, f, indent=2)
        logger.info("editions_catalog_saved", path=str(editions_path))

    # 3. Download info.json (grading metadata)
    info_path = dest / "info.json"
    download_file(INFO_URL, info_path)

    # 4. Filter English editions and download each
    keys = _english_edition_keys(editions_data)
    logger.info("english_editions_found", count=len(keys))

    downloaded: list[Path] = [editions_path, info_path]

    with httpx.Client(
        headers={"User-Agent": DEFAULT_USER_AGENT},
        timeout=120.0,
        follow_redirects=True,
    ) as client:
        for key in keys:
            url = EDITION_URL_TEMPLATE.format(key=key)
            edition_path = dest / f"{key}.json"
            download_file(url, edition_path, client=client, timeout=120.0)
            downloaded.append(edition_path)

    # 5. Validate minimum edition count
    edition_files = [p for p in dest.glob("eng-*.json")]
    if len(edition_files) < MIN_EXPECTED_EDITIONS:
        msg = (
            f"Expected >={MIN_EXPECTED_EDITIONS} English edition files, found {len(edition_files)}"
        )
        raise AssertionError(msg)

    logger.info("fawaz_acquired", edition_count=len(edition_files))
    write_manifest(dest, downloaded)
    return dest
