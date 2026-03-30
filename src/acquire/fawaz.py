"""Acquire hadith editions from the Fawaz Ahmed Hadith API CDN.

Downloads English and Arabic edition JSON files and grading metadata (info.json)
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


_EDITION_PREFIXES = ("eng-", "ara-")


def _edition_keys(editions: dict[str, Any] | list[Any]) -> list[str]:
    """Return edition keys that start with ``eng-`` or ``ara-``.

    Handles both the legacy flat dict format (key -> edition data) and the
    current nested format where each top-level key maps to an object with
    a ``collection`` list of edition objects containing a ``name`` field.
    """
    if not isinstance(editions, dict):
        return []

    # Check if any top-level key matches an edition prefix (legacy flat format).
    flat_keys = [k for k in editions if any(k.startswith(p) for p in _EDITION_PREFIXES)]
    if flat_keys:
        return sorted(flat_keys)

    # Current nested format: {collection_name: {name, collection: [{name, ...}, ...]}}.
    nested_keys: list[str] = []
    for _coll_name, coll_data in editions.items():
        if not isinstance(coll_data, dict):
            continue
        for edition in coll_data.get("collection", []):
            if not isinstance(edition, dict):
                continue
            name = edition.get("name", "")
            if any(name.startswith(p) for p in _EDITION_PREFIXES):
                nested_keys.append(name)
    return sorted(nested_keys)


def run(raw_dir: Path) -> Path:
    """Download Fawaz CDN editions (English + Arabic) and info.json.

    Idempotent — existing files are skipped.
    """
    dest = ensure_dir(raw_dir / "fawaz")

    # 1. Idempotency check — skip network requests if edition files already present
    existing_eng = list(dest.glob("eng-*.json"))
    existing_ara = list(dest.glob("ara-*.json"))
    if len(existing_eng) >= MIN_EXPECTED_EDITIONS and len(existing_ara) >= MIN_EXPECTED_EDITIONS:
        all_existing = existing_eng + existing_ara
        logger.info(
            "fawaz_already_acquired",
            eng_count=len(existing_eng),
            ara_count=len(existing_ara),
        )
        write_manifest(dest, all_existing)
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

    # 4. Filter English + Arabic editions and download each
    keys = _edition_keys(editions_data)
    logger.info("editions_found", count=len(keys))

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

    # 5. Validate minimum edition count for English and Arabic
    eng_files = list(dest.glob("eng-*.json"))
    if len(eng_files) < MIN_EXPECTED_EDITIONS:
        msg = f"Expected >={MIN_EXPECTED_EDITIONS} English edition files, found {len(eng_files)}"
        raise AssertionError(msg)

    ara_files = list(dest.glob("ara-*.json"))
    if len(ara_files) < MIN_EXPECTED_EDITIONS:
        logger.warning(
            "fawaz_low_arabic_editions",
            expected=MIN_EXPECTED_EDITIONS,
            found=len(ara_files),
        )
    logger.info(
        "fawaz_acquired",
        eng_count=len(eng_files),
        ara_count=len(ara_files),
    )
    write_manifest(dest, downloaded)
    return dest
