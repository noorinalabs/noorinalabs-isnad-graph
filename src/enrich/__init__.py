"""Phase 4: Graph metrics (centrality, PageRank, Louvain) and topic classification.

This package provides enrichment operations that compute derived properties
on the Neo4j graph using the Graph Data Science (GDS) library.
"""

from __future__ import annotations

import traceback
from pathlib import Path

from src.enrich.historical import run_historical_overlay
from src.enrich.metrics import run_metrics
from src.enrich.topics import run_topics
from src.models.enrich import EnrichSummary, HistoricalResult, MetricsResult, TopicResult
from src.utils.logging import get_logger
from src.utils.neo4j_client import Neo4jClient

__all__ = ["run_all", "run_metrics", "run_topics"]

log = get_logger(__name__)


def run_all(client: Neo4jClient, staging_dir: Path) -> EnrichSummary:
    """Run full enrichment pipeline: metrics -> topics -> historical."""
    steps_completed: list[str] = []
    steps_failed: list[str] = []
    metrics_result: MetricsResult | None = None
    topics_result: TopicResult | None = None
    historical_result: HistoricalResult | None = None

    # Metrics
    try:
        log.info("enrich_step_start", step="metrics")
        metrics_result = run_metrics(client)
        steps_completed.append("metrics")
        log.info("enrich_step_done", step="metrics")
    except Exception:
        steps_failed.append("metrics")
        log.error("enrich_step_failed", step="metrics", traceback=traceback.format_exc())

    # Topics
    try:
        log.info("enrich_step_start", step="topics")
        topics_result = run_topics(client, staging_dir)
        steps_completed.append("topics")
        log.info("enrich_step_done", step="topics")
    except Exception:
        steps_failed.append("topics")
        log.error("enrich_step_failed", step="topics", traceback=traceback.format_exc())

    # Historical overlay
    try:
        log.info("enrich_step_start", step="historical")
        historical_result = run_historical_overlay(client)
        steps_completed.append("historical")
        log.info("enrich_step_done", step="historical")
    except Exception:
        steps_failed.append("historical")
        log.error("enrich_step_failed", step="historical", traceback=traceback.format_exc())

    return EnrichSummary(
        metrics=metrics_result,
        topics=topics_result,
        historical=historical_result,
        steps_completed=steps_completed,
        steps_failed=steps_failed,
    )
