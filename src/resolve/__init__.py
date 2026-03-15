"""Phase 2: Entity Resolution pipeline."""

from __future__ import annotations

from pathlib import Path

from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["run_all"]


def run_all(
    raw_dir: Path, staging_dir: Path, output_dir: Path
) -> dict[str, list[Path]]:
    """Run full entity resolution pipeline: NER -> disambiguate -> dedup."""
    logger.info("resolve_pipeline_start")

    from src.resolve import dedup, disambiguate, ner

    results: dict[str, list[Path]] = {}

    # Step 1: NER
    logger.info("resolve_step", step="ner", status="not_yet_implemented")
    results["ner"] = ner.run(staging_dir, output_dir)

    # Step 2: Disambiguation
    logger.info("resolve_step", step="disambiguate", status="not_yet_implemented")
    results["disambiguate"] = disambiguate.run(staging_dir, output_dir)

    # Step 3: Deduplication
    logger.info("resolve_step", step="dedup", status="not_yet_implemented")
    results["dedup"] = dedup.run(staging_dir, output_dir)

    logger.info("resolve_pipeline_complete")
    return results
