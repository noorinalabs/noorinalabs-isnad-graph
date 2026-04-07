"""Admin system reports endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_neo4j
from src.api.models import (
    GraphValidationMetrics,
    SystemReportResponse,
    TopicCoverageMetrics,
)
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


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
    """Return aggregated system output reports.

    Pipeline, disambiguation, and dedup metrics are no longer available
    after ingestion extraction to noorinalabs-isnad-ingest-platform.
    """
    return SystemReportResponse(
        pipeline=None,
        disambiguation=None,
        dedup=None,
        graph_validation=_graph_validation_metrics(neo4j),
        topic_coverage=_topic_coverage_metrics(neo4j),
    )
