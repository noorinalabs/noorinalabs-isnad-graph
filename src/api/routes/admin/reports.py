"""Admin system reports endpoint."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from src.api.deps import get_neo4j
from src.api.models import (
    DedupMetrics,
    DisambiguationMetrics,
    GraphValidationMetrics,
    PipelineMetrics,
    SystemReportResponse,
    TopicCoverageMetrics,
)
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


def _pipeline_metrics() -> PipelineMetrics | None:
    """Collect pipeline parse/staging metrics from Parquet files."""
    from src.config import get_settings

    settings = get_settings()
    staging_dir = Path(settings.data_staging_dir)
    if not staging_dir.exists():
        return None

    try:
        from src.parse.validate import validate_staging

        report = validate_staging(staging_dir)
        return PipelineMetrics(
            total_files=report.total_files,
            total_rows=report.total_rows,
            files=[fr.model_dump(mode="json") for fr in report.files],
        )
    except Exception:  # noqa: BLE001
        return None


def _disambiguation_metrics() -> DisambiguationMetrics | None:
    """Collect disambiguation metrics from resolve output."""
    from src.config import get_settings

    settings = get_settings()
    staging_dir = Path(settings.data_staging_dir)
    output_dir = staging_dir / "resolved"
    if not output_dir.exists():
        return None

    try:
        from src.resolve import ResolveMetrics

        metrics = ResolveMetrics()
        from src.resolve import _collect_disambig_metrics, _collect_ner_metrics

        _collect_ner_metrics(metrics, output_dir)
        _collect_disambig_metrics(metrics, output_dir)

        if metrics.ner_mention_count > 0:
            resolved = metrics.ner_mention_count - metrics.ambiguous_count
            metrics.resolution_rate_pct = resolved / metrics.ner_mention_count * 100
            metrics.ambiguous_pct = metrics.ambiguous_count / metrics.ner_mention_count * 100

        return DisambiguationMetrics(
            ner_mention_count=metrics.ner_mention_count,
            canonical_narrator_count=metrics.canonical_narrator_count,
            ambiguous_count=metrics.ambiguous_count,
            resolution_rate_pct=round(metrics.resolution_rate_pct, 2),
            ambiguous_pct=round(metrics.ambiguous_pct, 2),
        )
    except Exception:  # noqa: BLE001
        return None


def _dedup_metrics() -> DedupMetrics | None:
    """Collect dedup/parallel metrics from staging output."""
    from src.config import get_settings

    settings = get_settings()
    staging_dir = Path(settings.data_staging_dir)
    path = staging_dir / "parallel_links.parquet"
    if not path.exists():
        return None

    try:
        from src.resolve import ResolveMetrics, _collect_dedup_metrics

        metrics = ResolveMetrics()
        _collect_dedup_metrics(metrics, staging_dir)
        return DedupMetrics(
            parallel_links_count=metrics.parallel_links_count,
            parallel_verbatim=metrics.parallel_verbatim,
            parallel_close_paraphrase=metrics.parallel_close_paraphrase,
            parallel_thematic=metrics.parallel_thematic,
            parallel_cross_sect=metrics.parallel_cross_sect,
        )
    except Exception:  # noqa: BLE001
        return None


def _graph_validation_metrics(neo4j: Neo4jClient) -> GraphValidationMetrics | None:
    """Query Neo4j for graph validation results."""
    try:
        query = """
            OPTIONAL MATCH (n:NARRATOR)
            WHERE NOT (n)-[:TRANSMITTED_TO]-() AND NOT (n)-[:NARRATED]-()
            WITH count(n) AS orphan_narrators
            OPTIONAL MATCH (h:HADITH)
            WHERE NOT (h)-[:APPEARS_IN]->(:COLLECTION)
            WITH orphan_narrators, count(h) AS orphan_hadiths
            OPTIONAL MATCH (c:CHAIN)
            WITH orphan_narrators, orphan_hadiths, count(c) AS total_chains
            OPTIONAL MATCH (c2:CHAIN) WHERE c2.is_complete = true
            WITH orphan_narrators, orphan_hadiths, total_chains,
                 count(c2) AS complete_chains
            OPTIONAL MATCH (h2:HADITH)
            WITH orphan_narrators, orphan_hadiths, total_chains, complete_chains,
                 count(h2) AS total_hadiths
            OPTIONAL MATCH (h3:HADITH)-[:APPEARS_IN]->(:COLLECTION)
            WITH orphan_narrators, orphan_hadiths, total_chains, complete_chains,
                 total_hadiths, count(DISTINCT h3) AS linked_hadiths
            RETURN orphan_narrators, orphan_hadiths,
                   CASE WHEN total_chains > 0
                        THEN toFloat(complete_chains) / toFloat(total_chains) * 100.0
                        ELSE 0.0 END AS chain_integrity_pct,
                   CASE WHEN total_hadiths > 0
                        THEN toFloat(linked_hadiths) / toFloat(total_hadiths) * 100.0
                        ELSE 0.0 END AS collection_coverage_pct
        """
        rows = neo4j.execute_read(query)
        if not rows:
            return None
        r = rows[0]
        return GraphValidationMetrics(
            orphan_narrators=r.get("orphan_narrators", 0),
            orphan_hadiths=r.get("orphan_hadiths", 0),
            chain_integrity_pct=round(r.get("chain_integrity_pct", 0.0), 2),
            collection_coverage_pct=round(r.get("collection_coverage_pct", 0.0), 2),
        )
    except Exception:  # noqa: BLE001
        return None


def _topic_coverage_metrics(neo4j: Neo4jClient) -> TopicCoverageMetrics | None:
    """Query Neo4j for topic classification coverage."""
    try:
        query = """
            OPTIONAL MATCH (h:HADITH)
            WITH count(h) AS total_hadiths
            OPTIONAL MATCH (h2:HADITH)
            WHERE size(h2.topic_tags) > 0
            RETURN total_hadiths, count(h2) AS classified_count,
                   CASE WHEN total_hadiths > 0
                        THEN toFloat(count(h2)) / toFloat(total_hadiths) * 100.0
                        ELSE 0.0 END AS coverage_pct
        """
        rows = neo4j.execute_read(query)
        if not rows:
            return None
        r = rows[0]
        return TopicCoverageMetrics(
            total_hadiths=r.get("total_hadiths", 0),
            classified_count=r.get("classified_count", 0),
            coverage_pct=round(r.get("coverage_pct", 0.0), 2),
        )
    except Exception:  # noqa: BLE001
        return None


@router.get("/reports", response_model=SystemReportResponse)
def system_reports(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> SystemReportResponse:
    """Return aggregated system output reports."""
    return SystemReportResponse(
        pipeline=_pipeline_metrics(),
        disambiguation=_disambiguation_metrics(),
        dedup=_dedup_metrics(),
        graph_validation=_graph_validation_metrics(neo4j),
        topic_coverage=_topic_coverage_metrics(neo4j),
    )
