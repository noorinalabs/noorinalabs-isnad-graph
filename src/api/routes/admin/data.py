"""Admin data-management endpoints.

Read-only views over the loaded graph for administrators: a node/edge
inventory ("what is loaded") and a provenance breakdown by source corpus
("where did it come from").  Write operations — pipeline reset, reprocess,
and per-source purge — are intentionally out of scope here and live behind
their own confirmation-gated surfaces.

All queries degrade gracefully to empty results when Neo4j is unavailable,
matching the analytics/reports admin endpoints.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from src.api.deps import get_neo4j
from src.utils.neo4j_client import Neo4jClient

router = APIRouter(prefix="/data")

log = structlog.get_logger(logger_name=__name__)


class NodeCount(BaseModel):
    """Count of nodes carrying a given label."""

    model_config = ConfigDict(frozen=True)

    label: str
    count: int


class RelationshipCount(BaseModel):
    """Count of relationships of a given type."""

    model_config = ConfigDict(frozen=True)

    rel_type: str
    count: int


class DataOverviewResponse(BaseModel):
    """Graph-wide node/edge inventory for the data-management panel."""

    model_config = ConfigDict(frozen=True)

    node_counts: list[NodeCount]
    relationship_counts: list[RelationshipCount]
    total_nodes: int
    total_relationships: int


class SourceBreakdown(BaseModel):
    """Loaded-content counts for a single source corpus."""

    model_config = ConfigDict(frozen=True)

    source_corpus: str
    hadith_count: int
    collection_count: int


class DataSourcesResponse(BaseModel):
    """Provenance breakdown of loaded content by source corpus."""

    model_config = ConfigDict(frozen=True)

    sources: list[SourceBreakdown]
    total_hadiths: int
    total_collections: int
    distinct_sources: int


def _node_counts(neo4j: Neo4jClient) -> list[NodeCount]:
    """Count nodes per label using the built-in ``db.labels()`` procedure.

    Label names come from the database catalog (not user input) and are
    backtick-quoted before interpolation.  Returns labels with at least one
    node, ordered by descending count.
    """
    try:
        records = neo4j.execute_read("CALL db.labels() YIELD label RETURN label")
        labels = [r["label"] for r in records]
    except Exception:  # noqa: BLE001
        log.debug("data_node_labels_failed")
        return []

    counts: list[NodeCount] = []
    for label in labels:
        try:
            records = neo4j.execute_read(f"MATCH (n:`{label}`) RETURN count(n) AS c")
        except Exception:  # noqa: BLE001
            log.debug("data_node_count_failed", label=label)
            continue
        count = records[0]["c"] if records else 0
        if count:
            counts.append(NodeCount(label=label, count=count))

    counts.sort(key=lambda c: c.count, reverse=True)
    return counts


def _relationship_counts(neo4j: Neo4jClient) -> list[RelationshipCount]:
    """Count relationships per type using ``db.relationshipTypes()``.

    Type names come from the database catalog and are backtick-quoted before
    interpolation.  Returns types with at least one edge, ordered by
    descending count.
    """
    try:
        types = [
            r["relationshipType"]
            for r in neo4j.execute_read(
                "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
            )
        ]
    except Exception:  # noqa: BLE001
        log.debug("data_rel_types_failed")
        return []

    counts: list[RelationshipCount] = []
    for rel_type in types:
        try:
            records = neo4j.execute_read(f"MATCH ()-[r:`{rel_type}`]->() RETURN count(r) AS c")
        except Exception:  # noqa: BLE001
            log.debug("data_rel_count_failed", rel_type=rel_type)
            continue
        count = records[0]["c"] if records else 0
        if count:
            counts.append(RelationshipCount(rel_type=rel_type, count=count))

    counts.sort(key=lambda c: c.count, reverse=True)
    return counts


@router.get("/overview", response_model=DataOverviewResponse)
def data_overview(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> DataOverviewResponse:
    """Return the node/edge inventory of the loaded graph.

    Degrades to empty lists / zero totals when Neo4j is unavailable.
    """
    node_counts = _node_counts(neo4j)
    relationship_counts = _relationship_counts(neo4j)

    return DataOverviewResponse(
        node_counts=node_counts,
        relationship_counts=relationship_counts,
        total_nodes=sum(c.count for c in node_counts),
        total_relationships=sum(c.count for c in relationship_counts),
    )


def _source_counts(neo4j: Neo4jClient, label: str) -> dict[str, int]:
    """Group nodes of ``label`` by their ``source_corpus`` property."""
    try:
        records = neo4j.execute_read(
            f"""
            MATCH (n:`{label}`)
            WHERE n.source_corpus IS NOT NULL
            RETURN n.source_corpus AS source, count(n) AS c
            """
        )
    except Exception:  # noqa: BLE001
        log.debug("data_source_count_failed", label=label)
        return {}
    return {r["source"]: r["c"] for r in records if r.get("source")}


@router.get("/sources", response_model=DataSourcesResponse)
def data_sources(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> DataSourcesResponse:
    """Return a provenance breakdown of loaded content by source corpus.

    Surfaces, for each corpus that contributed data, how many hadith and
    collection nodes it loaded.  Degrades to an empty breakdown when Neo4j is
    unavailable.
    """
    hadith_by_source = _source_counts(neo4j, "Hadith")
    collection_by_source = _source_counts(neo4j, "Collection")

    all_sources = sorted(set(hadith_by_source) | set(collection_by_source))
    sources = [
        SourceBreakdown(
            source_corpus=source,
            hadith_count=hadith_by_source.get(source, 0),
            collection_count=collection_by_source.get(source, 0),
        )
        for source in all_sources
    ]

    return DataSourcesResponse(
        sources=sources,
        total_hadiths=sum(hadith_by_source.values()),
        total_collections=sum(collection_by_source.values()),
        distinct_sources=len(all_sources),
    )
