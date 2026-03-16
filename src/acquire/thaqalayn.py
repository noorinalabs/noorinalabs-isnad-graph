"""Acquire hadith data from the Thaqalayn API.

Fetches Shia hadith collections via the Thaqalayn REST API (v2).
Falls back to cloning the ThaqalaynAPI GitHub repository if the API
returns too many consecutive server errors.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.acquire.base import clone_repo, ensure_dir, write_manifest
from src.utils.logging import get_logger

logger = get_logger(__name__)

THAQALAYN_API_BASE = "https://thaqalayn.net/api/v2"
THAQALAYN_GITHUB_URL = "https://github.com/MohammedArab1/ThaqalaynAPI.git"
REQUEST_DELAY_S = 0.5
MAX_CONSECUTIVE_5XX = 5
MIN_EXPECTED_BOOKS = 15


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def _fetch_json(url: str, client: httpx.Client) -> dict[str, Any] | list[Any]:
    """Fetch JSON with retry. Raises on HTTP error so tenacity can retry."""
    response = client.get(url)
    response.raise_for_status()
    result: dict[str, Any] | list[Any] = response.json()
    return result


def _download_via_api(dest: Path, client: httpx.Client) -> list[Path]:
    """Download all books via the Thaqalayn API. Returns list of saved files."""
    allbooks_url = f"{THAQALAYN_API_BASE}/allbooks"
    logger.info("thaqalayn_fetching_allbooks", url=allbooks_url)
    allbooks = _fetch_json(allbooks_url, client)

    allbooks_path = dest / "allbooks.json"
    allbooks_path.write_text(json.dumps(allbooks, ensure_ascii=False, indent=2), encoding="utf-8")
    saved: list[Path] = [allbooks_path]

    books: list[Any]
    if isinstance(allbooks, dict):
        books = allbooks.get("data", allbooks.get("books", [])) or []
    elif isinstance(allbooks, list):
        books = allbooks
    else:
        books = []

    logger.info("thaqalayn_books_found", count=len(books))
    consecutive_5xx = 0

    for book in books:
        book_id = book.get("id") or book.get("bookId") or book.get("_id")
        if book_id is None:
            logger.warning("thaqalayn_book_no_id", book=book)
            continue

        book_path = dest / f"book_{book_id}.json"
        if book_path.exists() and book_path.stat().st_size > 0:
            saved.append(book_path)
            consecutive_5xx = 0
            continue

        time.sleep(REQUEST_DELAY_S)

        try:
            url = f"{THAQALAYN_API_BASE}/hadith/{book_id}"
            data = _fetch_json(url, client)
            book_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            saved.append(book_path)
            consecutive_5xx = 0
            logger.info("thaqalayn_book_downloaded", book_id=book_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                consecutive_5xx += 1
                logger.warning(
                    "thaqalayn_5xx",
                    book_id=book_id,
                    status=exc.response.status_code,
                    consecutive=consecutive_5xx,
                )
                if consecutive_5xx >= MAX_CONSECUTIVE_5XX:
                    logger.error("thaqalayn_circuit_breaker_tripped")
                    raise
            else:
                logger.warning(
                    "thaqalayn_http_error",
                    book_id=book_id,
                    status=exc.response.status_code,
                )

    return saved


def _download_via_github(dest: Path) -> list[Path]:
    """Clone the ThaqalaynAPI repo as fallback. Returns JSON files found."""
    github_dest = dest / "github_clone"
    clone_repo(THAQALAYN_GITHUB_URL, github_dest)
    json_files = list(github_dest.rglob("*.json"))
    logger.info("thaqalayn_github_fallback", file_count=len(json_files))
    return json_files


def run(raw_dir: Path) -> Path:
    """Download Thaqalayn data. Uses API first, falls back to GitHub clone."""
    dest = ensure_dir(raw_dir / "thaqalayn")

    # Check for idempotent skip: already have enough book JSONs
    existing_books = list(dest.glob("book_*.json"))
    if len(existing_books) >= MIN_EXPECTED_BOOKS:
        logger.info(
            "thaqalayn_skipped",
            reason="already_acquired",
            book_count=len(existing_books),
        )
        write_manifest(dest, existing_books)
        return dest

    client = httpx.Client(
        headers={"User-Agent": "isnad-graph/1.0 (hadith-research)"},
        timeout=60.0,
        follow_redirects=True,
    )

    try:
        saved = _download_via_api(dest, client)
    except Exception:
        logger.warning("thaqalayn_api_failed_falling_back_to_github")
        saved = _download_via_github(dest)
    finally:
        client.close()

    book_files = [f for f in saved if f.name.startswith("book_")]
    if len(book_files) < MIN_EXPECTED_BOOKS:
        # API may have partially succeeded; try GitHub fallback
        if not (dest / "github_clone").exists():
            logger.warning("thaqalayn_insufficient_books_trying_github", count=len(book_files))
            github_files = _download_via_github(dest)
            saved.extend(github_files)
            book_files = [f for f in saved if f.name.startswith("book_")]

    all_json = [f for f in saved if f.suffix == ".json"]
    if len(book_files) < MIN_EXPECTED_BOOKS:
        msg = f"Expected >= {MIN_EXPECTED_BOOKS} book JSONs, found {len(book_files)}"
        raise AssertionError(msg)

    write_manifest(dest, all_json)
    logger.info("thaqalayn_acquired", book_count=len(book_files), total_files=len(all_json))
    return dest
