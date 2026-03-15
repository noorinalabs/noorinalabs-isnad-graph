"""Narrator Named Entity Recognition from isnad chains."""

from __future__ import annotations

from pathlib import Path

from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["run"]


def run(staging_dir: Path, output_dir: Path) -> list[Path]:
    """Extract narrator mentions from parsed isnad chains.

    Reads staging Parquet files and produces resolved narrator mention tables.
    """
    logger.info("ner_run", status="not_yet_implemented")
    return []
