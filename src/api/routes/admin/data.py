"""Admin data-management endpoints.

Read-only views over the loaded graph for administrators: a node/edge
inventory ("what is loaded") and a provenance breakdown by source corpus
("where did it come from").

This module also hosts the **per-source graph purge** (ig#989) — a
destructive, admin-only DETACH DELETE of every node carrying a given
``source_corpus`` provenance, behind a dry-run preview and a typed-confirmation
gate.  This is GRAPH-level removal, distinct from the cross-service
ingest-platform pipeline reset (ig#970, ``/admin/reset/*`` on the ingest
origin): the reset wipes the staging/pipeline store, this wipes loaded Neo4j
nodes/edges.  The two surfaces do not overlap.

The read-only views degrade gracefully to empty results when Neo4j is
unavailable, matching the analytics/reports admin endpoints.  The purge's
real-run DETACH DELETE deliberately does NOT swallow Neo4j errors — a failed
destructive write surfaces as 503 rather than silently reporting success.
"""

from __future__ import annotations

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from src.api.auth import User
from src.api.deps import get_bearer_token, get_neo4j
from src.api.middleware import require_admin
from src.api.routes.admin.audit import create_audit_entry
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


# ---------------------------------------------------------------------------
# Per-source graph purge (ig#989) — destructive, admin-only.
# ---------------------------------------------------------------------------


class PurgeRequest(BaseModel):
    """Request to purge all graph data carrying a single source corpus.

    ``dry_run`` (the default) returns a preview of what WOULD be removed and
    touches nothing.  A real run additionally requires ``confirmation`` to echo
    ``source_corpus`` exactly — the per-source analogue of the ig#970 reset's
    typed OBLITERATE token (a destructive action must be deliberately confirmed,
    never fired by a single click).  ``extra="forbid"`` rejects unknown fields
    so a malformed body 422s before the handler runs.
    """

    model_config = ConfigDict(extra="forbid")

    source_corpus: str
    dry_run: bool = True
    confirmation: str | None = None


class PurgeResult(BaseModel):
    """Preview (dry run) or outcome (real run) of a per-source purge.

    ``node_counts`` / ``relationship_counts`` describe the graph data scoped to
    ``source_corpus`` — what would be removed on a dry run, or what was removed
    on a real run.  ``deleted`` is False for a dry run and True once the
    DETACH DELETE has executed.
    """

    model_config = ConfigDict(frozen=True)

    source_corpus: str
    node_counts: list[NodeCount]
    relationship_counts: list[RelationshipCount]
    total_nodes: int
    total_relationships: int
    dry_run: bool
    deleted: bool


def _purge_node_counts(neo4j: Neo4jClient, corpus: str) -> list[NodeCount]:
    """Count, per label, the nodes carrying ``source_corpus == corpus``.

    Provenance is matched on the ``source_corpus`` property — the same property
    the inventory groups on — so the purge removes exactly the nodes the
    ``/data/sources`` breakdown attributes to this corpus.  Degrades to an empty
    list when Neo4j is unavailable.
    """
    try:
        records = neo4j.execute_read(
            """
            MATCH (n)
            WHERE n.source_corpus = $corpus
            UNWIND labels(n) AS label
            RETURN label, count(*) AS c
            """,
            {"corpus": corpus},
        )
    except Exception:  # noqa: BLE001
        log.debug("data_purge_node_count_failed", source_corpus=corpus)
        return []

    counts = [NodeCount(label=r["label"], count=r["c"]) for r in records if r.get("c")]
    counts.sort(key=lambda c: c.count, reverse=True)
    return counts


def _purge_relationship_counts(neo4j: Neo4jClient, corpus: str) -> list[RelationshipCount]:
    """Count, per type, the relationships incident to purged nodes.

    DETACH DELETE removes every edge touching a deleted node, so we count edges
    with at least one endpoint carrying ``source_corpus == corpus``.  The
    undirected match plus ``count(DISTINCT r)`` avoids double-counting an edge
    whose BOTH endpoints belong to the corpus.  Degrades to an empty list when
    Neo4j is unavailable.
    """
    try:
        records = neo4j.execute_read(
            """
            MATCH (n)-[r]-()
            WHERE n.source_corpus = $corpus
            RETURN type(r) AS rel_type, count(DISTINCT r) AS c
            """,
            {"corpus": corpus},
        )
    except Exception:  # noqa: BLE001
        log.debug("data_purge_rel_count_failed", source_corpus=corpus)
        return []

    counts = [
        RelationshipCount(rel_type=r["rel_type"], count=r["c"])
        for r in records
        if r.get("c") and r.get("rel_type")
    ]
    counts.sort(key=lambda c: c.count, reverse=True)
    return counts


@router.post("/purge", response_model=PurgeResult)
def purge_source(
    body: PurgeRequest,
    admin: User = Depends(require_admin),
    neo4j: Neo4jClient = Depends(get_neo4j),
    token: str = Depends(get_bearer_token),
) -> PurgeResult:
    """Purge all graph data for a single source corpus.

    Two-phase, mirroring the reset UX:

    * **Dry run** (``dry_run=True``, the default) — returns the node/edge counts
      that WOULD be removed and touches nothing.
    * **Real run** (``dry_run=False``) — requires ``confirmation`` to equal
      ``source_corpus`` exactly, then ``DETACH DELETE``s every node carrying
      that provenance (and, via DETACH, all their edges) and writes an audit
      entry.

    Admin-only (the router group is gated by ``require_admin``; the explicit
    dependency here also supplies the actor identity for the audit trail).
    """
    corpus = body.source_corpus.strip()
    if not corpus:
        raise HTTPException(status_code=422, detail="source_corpus is required")

    node_counts = _purge_node_counts(neo4j, corpus)
    relationship_counts = _purge_relationship_counts(neo4j, corpus)
    total_nodes = sum(c.count for c in node_counts)
    total_relationships = sum(c.count for c in relationship_counts)

    if body.dry_run:
        return PurgeResult(
            source_corpus=corpus,
            node_counts=node_counts,
            relationship_counts=relationship_counts,
            total_nodes=total_nodes,
            total_relationships=total_relationships,
            dry_run=True,
            deleted=False,
        )

    # Real run — typed-confirmation gate: the caller must echo the exact corpus.
    if body.confirmation != corpus:
        raise HTTPException(
            status_code=400,
            detail="Confirmation does not match source_corpus; purge aborted.",
        )

    try:
        neo4j.execute_write(
            "MATCH (n) WHERE n.source_corpus = $corpus DETACH DELETE n",
            {"corpus": corpus},
        )
    except Exception as exc:  # noqa: BLE001
        # Unlike the read-only views, a destructive write must NOT degrade to a
        # silent "success" — surface the failure so the admin knows the graph
        # was not modified.
        log.error("data_purge_failed", source_corpus=corpus, error=str(exc))
        raise HTTPException(
            status_code=503,
            detail="Graph store unavailable; purge was not completed.",
        ) from exc

    # Best-effort audit: the destructive purge has already succeeded, so a
    # failure to record the audit entry (user-service unreachable / erroring)
    # must NOT turn a completed action into a 5xx. Log loudly and continue.
    try:
        create_audit_entry(
            token,
            action="data.purge_source",
            actor_id=admin.id,
            actor_name=admin.name,
            details=(
                f"Purged source_corpus '{corpus}': "
                f"{total_nodes} nodes, {total_relationships} relationships removed."
            ),
        )
    except httpx.HTTPError as exc:
        log.error(
            "data_purge_audit_failed",
            source_corpus=corpus,
            actor_id=admin.id,
            error=str(exc),
        )
    log.info(
        "data_purge_executed",
        source_corpus=corpus,
        nodes=total_nodes,
        relationships=total_relationships,
        actor_id=admin.id,
    )

    return PurgeResult(
        source_corpus=corpus,
        node_counts=node_counts,
        relationship_counts=relationship_counts,
        total_nodes=total_nodes,
        total_relationships=total_relationships,
        dry_run=False,
        deleted=True,
    )
