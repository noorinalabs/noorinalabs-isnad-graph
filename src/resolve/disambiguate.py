"""Narrator disambiguation via multi-stage matching."""

from __future__ import annotations

from pathlib import Path

from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["run"]


def run(staging_dir: Path, output_dir: Path) -> list[Path]:
    """Disambiguate narrator mentions to canonical narrator records.

    Multi-stage pipeline: exact match, fuzzy match, embedding similarity.
    """
    logger.info("disambiguate_run", status="not_yet_implemented")
    return []
