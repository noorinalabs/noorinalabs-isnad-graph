"""Phase 2: Entity Resolution pipeline.

Dependency-aware orchestrator: NER -> disambiguate -> dedup.
Dedup runs independently of NER/disambiguation (only needs hadith text).
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from pathlib import Path

from src.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["ResolveMetrics", "run_all"]


@dataclass
class ResolveMetrics:
    """Typed metrics returned by the resolve pipeline."""

    ner_mention_count: int = 0
    canonical_narrator_count: int = 0
    ambiguous_count: int = 0
    resolution_rate_pct: float = 0.0
    ambiguous_pct: float = 0.0
    parallel_links_count: int = 0
    parallel_verbatim: int = 0
    parallel_close_paraphrase: int = 0
    parallel_thematic: int = 0
    parallel_cross_sect: int = 0
    ner_files: list[Path] = field(default_factory=list)
    disambiguate_files: list[Path] = field(default_factory=list)
    dedup_files: list[Path] = field(default_factory=list)

    def summary(self) -> str:
        """Return a human-readable summary string."""
        lines = [
            "=== Phase 2: Entity Resolution Summary ===",
            f"  NER mentions extracted   : {self.ner_mention_count}",
            f"  Canonical narrators      : {self.canonical_narrator_count}",
            f"  Ambiguous mentions       : {self.ambiguous_count}",
            f"  Resolution rate          : {self.resolution_rate_pct:.1f}%",
            f"  Ambiguous %              : {self.ambiguous_pct:.1f}%",
            f"  Parallel links           : {self.parallel_links_count}",
        ]
        if self.parallel_links_count > 0:
            lines.extend([
                f"    verbatim               : {self.parallel_verbatim}",
                f"    close paraphrase       : {self.parallel_close_paraphrase}",
                f"    thematic               : {self.parallel_thematic}",
                f"    cross-sect             : {self.parallel_cross_sect}",
            ])
        total_files = (
            len(self.ner_files) + len(self.disambiguate_files) + len(self.dedup_files)
        )
        lines.append(f"  Output files             : {total_files}")
        return "\n".join(lines)


def _has_staging_parquets(staging_dir: Path) -> bool:
    """Check that staging directory contains at least one Parquet file."""
    return any(staging_dir.glob("**/*.parquet"))


def _collect_dedup_metrics(metrics: ResolveMetrics, staging_dir: Path) -> None:
    """Read parallel_links.parquet to populate dedup metrics."""
    path = staging_dir / "parallel_links.parquet"
    if not path.exists():
        return
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(path)
        metrics.parallel_links_count = table.num_rows
        if table.num_rows > 0:
            vt_col = table.column("variant_type")
            cs_col = table.column("cross_sect")
            for i in range(table.num_rows):
                vt = vt_col[i].as_py()
                if vt == "verbatim":
                    metrics.parallel_verbatim += 1
                elif vt == "close_paraphrase":
                    metrics.parallel_close_paraphrase += 1
                elif vt == "thematic":
                    metrics.parallel_thematic += 1
                if cs_col[i].as_py():
                    metrics.parallel_cross_sect += 1
    except Exception:  # noqa: BLE001
        logger.warning("dedup_metrics_read_failed", path=str(path))


def _collect_disambig_metrics(metrics: ResolveMetrics, output_dir: Path) -> None:
    """Read disambiguation outputs to populate narrator metrics."""
    canonical_path = output_dir / "narrators_canonical.parquet"
    ambiguous_path = output_dir / "ambiguous_narrators.csv"

    try:
        if canonical_path.exists():
            import pyarrow.parquet as pq

            table = pq.read_table(canonical_path)
            metrics.canonical_narrator_count = table.num_rows
    except Exception:  # noqa: BLE001
        logger.warning("canonical_metrics_read_failed", path=str(canonical_path))

    try:
        if ambiguous_path.exists():
            import csv

            with open(ambiguous_path, encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                metrics.ambiguous_count = sum(1 for _ in reader)
    except Exception:  # noqa: BLE001
        logger.warning("ambiguous_metrics_read_failed", path=str(ambiguous_path))


def _collect_ner_metrics(metrics: ResolveMetrics, output_dir: Path) -> None:
    """Read NER output to populate mention count."""
    path = output_dir / "narrator_mentions_resolved.parquet"
    if not path.exists():
        return
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(path)
        metrics.ner_mention_count = table.num_rows
    except Exception:  # noqa: BLE001
        logger.warning("ner_metrics_read_failed", path=str(path))


def run_all(
    raw_dir: Path, staging_dir: Path, output_dir: Path
) -> dict[str, list[Path]]:
    """Run full entity resolution pipeline: NER -> disambiguate -> dedup.

    Dependency-aware: if NER fails, skip disambiguation but still run dedup
    (dedup only needs hadith text, not narrator mentions).
    """
    logger.info("resolve_pipeline_start")

    from src.resolve import dedup, disambiguate, ner

    results: dict[str, list[Path]] = {"ner": [], "disambiguate": [], "dedup": []}

    # Pre-flight check: verify staging has Parquet files.
    if not staging_dir.exists() or not _has_staging_parquets(staging_dir):
        logger.warning(
            "resolve_preflight_failed",
            staging_dir=str(staging_dir),
            msg="No Parquet files found in staging directory",
        )
        print("Resolution skipped: no staging Parquet files found.")
        return results

    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: NER
    ner_ok = False
    try:
        logger.info("resolve_step", step="ner", status="running")
        results["ner"] = ner.run(staging_dir, output_dir)
        ner_ok = True
        logger.info("resolve_step", step="ner", status="complete", files=len(results["ner"]))
    except Exception:  # noqa: BLE001
        logger.error("resolve_step_failed", step="ner", traceback=traceback.format_exc())

    # Step 2: Disambiguation (skip if NER failed — needs mention output).
    if ner_ok:
        try:
            logger.info("resolve_step", step="disambiguate", status="running")
            results["disambiguate"] = disambiguate.run(staging_dir, output_dir)
            logger.info(
                "resolve_step",
                step="disambiguate",
                status="complete",
                files=len(results["disambiguate"]),
            )
        except Exception:  # noqa: BLE001
            logger.error(
                "resolve_step_failed",
                step="disambiguate",
                traceback=traceback.format_exc(),
            )
    else:
        logger.warning(
            "resolve_step_skipped",
            step="disambiguate",
            reason="NER failed — no mention data available",
        )

    # Step 3: Dedup (runs independently of NER/disambiguation).
    try:
        logger.info("resolve_step", step="dedup", status="running")
        results["dedup"] = dedup.run(staging_dir, output_dir)
        logger.info(
            "resolve_step", step="dedup", status="complete", files=len(results["dedup"])
        )
    except Exception:  # noqa: BLE001
        logger.error(
            "resolve_step_failed", step="dedup", traceback=traceback.format_exc()
        )

    # Collect metrics from output files.
    metrics = ResolveMetrics(
        ner_files=results["ner"],
        disambiguate_files=results["disambiguate"],
        dedup_files=results["dedup"],
    )
    _collect_ner_metrics(metrics, output_dir)
    _collect_disambig_metrics(metrics, output_dir)
    _collect_dedup_metrics(metrics, staging_dir)

    # Compute derived rates.
    if metrics.ner_mention_count > 0:
        resolved = metrics.ner_mention_count - metrics.ambiguous_count
        metrics.resolution_rate_pct = resolved / metrics.ner_mention_count * 100
        metrics.ambiguous_pct = metrics.ambiguous_count / metrics.ner_mention_count * 100

    logger.info(
        "resolve_pipeline_complete",
        ner_mentions=metrics.ner_mention_count,
        canonical_narrators=metrics.canonical_narrator_count,
        ambiguous=metrics.ambiguous_count,
        resolution_rate_pct=round(metrics.resolution_rate_pct, 1),
        parallel_links=metrics.parallel_links_count,
    )

    print(metrics.summary())

    return results
