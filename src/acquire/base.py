"""Shared utilities for data acquisition."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "ensure_dir",
    "download_file",
    "fetch_json",
    "fetch_json_paginated",
    "clone_repo",
    "sha256_file",
    "write_manifest",
]

DEFAULT_USER_AGENT = "isnad-graph/1.0 (hadith-research)"
DEFAULT_TIMEOUT = 60.0

# Type alias for paginated response parser callbacks.
ResponseParser = Callable[[dict[str, Any] | list[Any]], tuple[list[dict[str, Any]], int | None]]


def ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist, return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def download_file(
    url: str,
    dest: Path,
    *,
    overwrite: bool = False,
    expected_sha256: str | None = None,
    client: httpx.Client | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Path:
    """Download file via httpx streaming.

    Skip if *dest* already exists (non-empty) and *overwrite* is ``False``.
    Verify SHA-256 if *expected_sha256* is provided.
    """
    if dest.exists() and dest.stat().st_size > 0 and not overwrite:
        logger.info("download_skipped", path=str(dest), reason="already_exists")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    own_client = client is None
    _client = client or httpx.Client(
        headers={"User-Agent": DEFAULT_USER_AGENT},
        timeout=timeout,
        follow_redirects=True,
    )

    try:
        with _client.stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            with open(dest, "wb") as f:
                with tqdm(
                    total=total, unit="B", unit_scale=True, desc=dest.name, disable=total == 0
                ) as pbar:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

        if expected_sha256:
            actual = sha256_file(dest)
            if actual != expected_sha256:
                dest.unlink()
                msg = f"SHA-256 mismatch: expected {expected_sha256}, got {actual}"
                raise ValueError(msg)

        logger.info("download_complete", path=str(dest), size=dest.stat().st_size)
        return dest
    except Exception:
        # Remove partial file so tenacity retries on a clean slate.
        if dest.exists():
            dest.unlink()
        raise
    finally:
        if own_client:
            _client.close()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
def fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> dict[str, Any] | list[Any]:
    """Fetch JSON from *url* with retry logic."""
    own_client = client is None
    _client = client or httpx.Client(
        headers={"User-Agent": DEFAULT_USER_AGENT},
        timeout=timeout,
        follow_redirects=True,
    )

    try:
        all_headers = {"User-Agent": DEFAULT_USER_AGENT}
        if headers:
            all_headers.update(headers)
        response = _client.get(url, headers=all_headers)
        response.raise_for_status()
        result: dict[str, Any] | list[Any] = response.json()
        return result
    finally:
        if own_client:
            _client.close()


def fetch_json_paginated(
    base_url: str,
    *,
    headers: dict[str, str] | None = None,
    page_param: str = "page",
    limit_param: str = "limit",
    limit: int = 50,
    max_pages: int = 1000,
    data_key: str = "data",
    total_key: str = "total",
    response_parser: ResponseParser | None = None,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Fetch all pages from a paginated JSON API.

    If *response_parser* is provided, it is called with the raw response dict
    and must return ``(items_list, total_or_none)``.  This is the escape hatch
    for non-standard pagination schemes.
    """
    all_results: list[dict[str, Any]] = []
    page = 1

    while page <= max_pages:
        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}{page_param}={page}&{limit_param}={limit}"

        raw = fetch_json(url, headers=headers, client=client)

        if response_parser is not None:
            items, total = response_parser(raw)
        elif isinstance(raw, dict):
            items = raw.get(data_key, [])
            total = raw.get(total_key)
        else:
            items = raw
            total = None

        if not items:
            break

        all_results.extend(items)

        if page % 10 == 0:
            logger.info("paginated_fetch_progress", page=page, accumulated=len(all_results))

        if total is not None and len(all_results) >= int(total):
            break

        page += 1

    logger.info("paginated_fetch_complete", total_items=len(all_results), pages=page)
    return all_results


def clone_repo(
    repo_url: str,
    dest: Path,
    *,
    shallow: bool = True,
    overwrite: bool = False,
) -> Path:
    """Clone a git repository. Use ``--depth 1`` if *shallow*. 120 s timeout."""
    if dest.exists() and any(dest.iterdir()) and not overwrite:
        logger.info("clone_skipped", dest=str(dest), reason="already_exists")
        return dest

    dest.mkdir(parents=True, exist_ok=True)
    cmd: list[str] = ["git", "clone"]
    if shallow:
        cmd.extend(["--depth", "1"])
    cmd.extend([repo_url, str(dest)])

    try:
        subprocess.run(  # noqa: S603
            cmd,
            timeout=120,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("clone_complete", dest=str(dest), url=repo_url)
    except subprocess.TimeoutExpired:
        logger.error("clone_timeout", url=repo_url, timeout=120)
        raise
    except subprocess.CalledProcessError as e:
        logger.error("clone_failed", url=repo_url, stderr=e.stderr)
        raise

    return dest


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(dest_dir: Path, files: list[Path]) -> Path:
    """Write ``manifest.json`` listing files with sizes and SHA-256 hashes."""
    manifest: list[dict[str, str | int]] = []
    for f in files:
        manifest.append(
            {
                "path": str(f.relative_to(dest_dir)),
                "size": f.stat().st_size,
                "sha256": sha256_file(f),
            }
        )

    manifest_path = dest_dir / "manifest.json"
    with open(manifest_path, "w") as fp:
        json.dump(manifest, fp, indent=2)

    logger.info("manifest_written", path=str(manifest_path), file_count=len(manifest))
    return manifest_path
