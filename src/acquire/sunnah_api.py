"""Acquire hadith data from the Sunnah.com REST API.

Fetches collection metadata and paginated hadith records for each collection.
Requires ``SUNNAH_API_KEY`` in the environment; gracefully skips if missing.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from src.acquire.base import ensure_dir, fetch_json_paginated, write_manifest
from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://api.sunnah.com/v1"
RATE_LIMIT_SECONDS = 0.2


def run(raw_dir: Path) -> Path | None:
    """Download all collections and hadiths from Sunnah.com API.

    Returns the output directory on success, or ``None`` if the API key
    is not configured.
    """
    api_key = get_settings().sunnah_api_key
    if not api_key:
        logger.warning("sunnah_api_skipped", reason="SUNNAH_API_KEY not set")
        return None

    dest = ensure_dir(raw_dir / "sunnah")
    headers = {"X-API-Key": api_key}

    # 1. Fetch collection list
    collections_path = dest / "collections.json"
    if not collections_path.exists() or collections_path.stat().st_size == 0:
        raw_collections = fetch_json_paginated(
            f"{BASE_URL}/collections",
            headers=headers,
            limit=50,
        )
        with open(collections_path, "w", encoding="utf-8") as f:
            json.dump(raw_collections, f, ensure_ascii=False, indent=2)
        logger.info("sunnah_collections_saved", count=len(raw_collections))
    else:
        with open(collections_path, encoding="utf-8") as f:
            raw_collections = json.load(f)
        logger.info("sunnah_collections_cached", count=len(raw_collections))

    # 2. Fetch hadiths per collection
    saved_files: list[Path] = [collections_path]
    total_hadiths = 0

    for collection in raw_collections:
        name: str = collection.get("name", collection.get("collection", ""))
        if not name:
            logger.warning("sunnah_collection_no_name", collection=collection)
            continue

        hadiths_path = dest / f"{name}_hadiths.json"
        if hadiths_path.exists() and hadiths_path.stat().st_size > 0:
            logger.info("sunnah_hadiths_cached", collection=name)
            saved_files.append(hadiths_path)
            continue

        time.sleep(RATE_LIMIT_SECONDS)

        hadiths = fetch_json_paginated(
            f"{BASE_URL}/collections/{name}/hadiths",
            headers=headers,
            limit=100,
        )

        with open(hadiths_path, "w", encoding="utf-8") as f:
            json.dump(hadiths, f, ensure_ascii=False, indent=2)

        saved_files.append(hadiths_path)
        total_hadiths += len(hadiths)
        logger.info("sunnah_hadiths_saved", collection=name, count=len(hadiths))

        time.sleep(RATE_LIMIT_SECONDS)

    write_manifest(dest, saved_files)
    logger.info(
        "sunnah_acquired",
        collections=len(raw_collections),
        total_hadiths=total_hadiths,
    )
    return dest
