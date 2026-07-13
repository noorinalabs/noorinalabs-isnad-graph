"""Graph traversal and visualization endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_neo4j
from src.api.models import (
    ChainSummary,
    ChainVisualization,
    GraphEdge,
    GraphNode,
    NarratorChainsResponse,
    NarratorNetworkResponse,
)
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


@router.get(
    "/graph/narrator/{narrator_id}/chains",
    response_model=NarratorChainsResponse,
)
def get_narrator_chains(
    narrator_id: str,
    limit: int = Query(20, ge=1, le=100),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> NarratorChainsResponse:
    """Return the isnad chains (hadiths) a narrator appears in.

    A narrator "appears in" a hadith's isnad when they either directly
    ``NARRATED`` the hadith or are an endpoint of one of that hadith's
    ``TRANSMITTED_TO`` edges. Those edges carry ``hadith_id`` and
    ``position_in_chain`` — the per-hadith chain lives on the edge properties,
    not on reified ``Chain`` nodes (there are none in the graph; see #1032).

    Each returned row summarises one hadith whose chain includes this narrator.
    The chain is identified by its hadith id (``chain_id == hadith_id``); the
    full ordered chain for a hadith is available from
    ``GET /graph/hadith/{hadith_id}/chain``.
    """
    # Verify narrator exists
    exists = neo4j.execute_read(
        "MATCH (n:Narrator {id: $id}) RETURN n.id AS id",
        {"id": narrator_id},
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Narrator '{narrator_id}' not found")

    # Isnad membership is recorded two ways, both keyed off the narrator: a
    # direct NARRATED edge, or any TRANSMITTED_TO edge tagged with the hadith
    # id. The UNION-ed subquery collects both, DISTINCT de-duplicates hadiths
    # reached by both paths, and ORDER BY / LIMIT run over the merged set.
    rows = neo4j.execute_read(
        """
        CALL {
            MATCH (n:Narrator {id: $id})-[:NARRATED]->(h:Hadith)
            RETURN h
            UNION
            MATCH (n:Narrator {id: $id})-[t:TRANSMITTED_TO]-(:Narrator)
            MATCH (h:Hadith {id: t.hadith_id})
            RETURN h
        }
        WITH DISTINCT h
        RETURN h.id AS hadith_id, h.matn_ar AS matn_ar, h.matn_en AS matn_en,
               coalesce(h.grade_composite, h.grade) AS grade
        ORDER BY h.id
        LIMIT $limit
        """,
        {"id": narrator_id, "limit": limit},
    )
    chains = [
        ChainSummary(
            chain_id=r["hadith_id"],
            hadith_id=r["hadith_id"],
            matn_ar=r["matn_ar"],
            matn_en=r.get("matn_en"),
            grade=r.get("grade"),
        )
        for r in rows
    ]
    return NarratorChainsResponse(narrator_id=narrator_id, chains=chains, total=len(chains))


@router.get(
    "/graph/hadith/{hadith_id}/chain",
    response_model=ChainVisualization,
)
def get_hadith_chain(
    hadith_id: str,
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> ChainVisualization:
    """Return the ordered isnad chain for a hadith (nodes + edges for D3/vis.js).

    The chain is reconstructed from the hadith's own ``TRANSMITTED_TO`` edges,
    which carry ``hadith_id`` and ``position_in_chain``. There are no reified
    ``Chain`` nodes in the graph (#1032), so the chain *is* the set of edges
    tagged with this hadith id. Edges are returned ordered by
    ``position_in_chain`` (carried on each edge as ``position``) so the consumer
    can render the chain in transmission order.
    """
    exists = neo4j.execute_read(
        "MATCH (h:Hadith {id: $id}) RETURN h.id AS id",
        {"id": hadith_id},
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Hadith '{hadith_id}' not found")

    # A hadith's isnad is the TRANSMITTED_TO edges tagged with its id, ordered
    # by position_in_chain. Each edge links two consecutive narrators in the
    # chain; the node set is the union of those edges' endpoints.
    rows = neo4j.execute_read(
        """
        MATCH (src:Narrator)-[t:TRANSMITTED_TO {hadith_id: $id}]->(tgt:Narrator)
        RETURN t.position_in_chain AS position,
               src.id AS source_id, src.name_ar AS source_name_ar,
               src.name_en AS source_name_en, src.generation AS source_gen,
               tgt.id AS target_id, tgt.name_ar AS target_name_ar,
               tgt.name_en AS target_name_en, tgt.generation AS target_gen
        ORDER BY t.position_in_chain
        """,
        {"id": hadith_id},
    )

    seen_nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    for r in rows:
        for prefix in ("source", "target"):
            nid = r[f"{prefix}_id"]
            if nid not in seen_nodes:
                seen_nodes[nid] = GraphNode(
                    id=nid,
                    label=r.get(f"{prefix}_name_en") or r[f"{prefix}_name_ar"],
                    name_ar=r[f"{prefix}_name_ar"],
                    name_en=r.get(f"{prefix}_name_en"),
                    type="narrator",
                    generation=r.get(f"{prefix}_gen"),
                )
        edges.append(
            GraphEdge(
                source=r["source_id"],
                target=r["target_id"],
                relationship="TRANSMITTED_TO",
                position=r.get("position"),
            )
        )

    return ChainVisualization(
        hadith_id=hadith_id,
        nodes=list(seen_nodes.values()),
        edges=edges,
    )


def _row_to_graph_node(row: dict[str, Any], prefix: str = "") -> GraphNode:
    """Convert a Cypher result row to a GraphNode, reading prefixed columns."""
    p = prefix
    return GraphNode(
        id=row[f"{p}id"],
        label=row.get(f"{p}name_en") or row[f"{p}name_ar"],
        name_ar=row[f"{p}name_ar"],
        name_en=row.get(f"{p}name_en"),
        type="narrator",
        generation=row.get(f"{p}gen"),
        community_id=row.get(f"{p}community_id"),
        in_degree=row.get(f"{p}in_degree"),
        out_degree=row.get(f"{p}out_degree"),
        betweenness_centrality=row.get(f"{p}betweenness_centrality"),
        pagerank=row.get(f"{p}pagerank"),
        sect_affiliation=row.get(f"{p}sect_affiliation"),
        trustworthiness_consensus=row.get(f"{p}trustworthiness_consensus"),
        death_year_ah=row.get(f"{p}death_year_ah"),
        birth_year_ah=row.get(f"{p}birth_year_ah"),
        kunya=row.get(f"{p}kunya"),
        nisba=row.get(f"{p}nisba"),
        # Absent property comes back as null → coerce to the false default so an
        # unflagged (or older) node discloses "not over-merged" rather than 500ing.
        over_merged=bool(row.get(f"{p}over_merged")),
        over_merge_note=row.get(f"{p}over_merge_note"),
    )


_NARRATOR_FIELDS = """
    n.id AS {p}id, n.name_ar AS {p}name_ar, n.name_en AS {p}name_en,
    n.generation AS {p}gen, n.community_id AS {p}community_id,
    n.in_degree AS {p}in_degree, n.out_degree AS {p}out_degree,
    n.betweenness_centrality AS {p}betweenness_centrality,
    n.pagerank AS {p}pagerank, n.sect_affiliation AS {p}sect_affiliation,
    n.trustworthiness_consensus AS {p}trustworthiness_consensus,
    n.death_year_ah AS {p}death_year_ah, n.birth_year_ah AS {p}birth_year_ah,
    n.kunya AS {p}kunya, n.nisba AS {p}nisba,
    n.over_merged AS {p}over_merged, n.over_merge_note AS {p}over_merge_note
"""


@router.get(
    "/graph/narrator/{narrator_id}/network",
    response_model=NarratorNetworkResponse,
)
def get_narrator_network(
    narrator_id: str,
    depth: int = Query(1, ge=1, le=3),
    limit: int = Query(200, ge=1, le=500),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> NarratorNetworkResponse:
    """Return ego network at given depth from a narrator."""
    exists = neo4j.execute_read(
        "MATCH (n:Narrator {id: $id}) RETURN n.id AS id",
        {"id": narrator_id},
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Narrator '{narrator_id}' not found")

    # Fetch center node with all fields
    center_fields = _NARRATOR_FIELDS.format(p="")
    center_rows: list[dict[str, Any]] = neo4j.execute_read(
        f"MATCH (n:Narrator {{id: $id}}) RETURN {center_fields}",
        {"id": narrator_id},
    )
    if not center_rows:
        return NarratorNetworkResponse(
            narrator_id=narrator_id, nodes=[], edges=[], teachers=0, students=0
        )

    seen_nodes: dict[str, GraphNode] = {narrator_id: _row_to_graph_node(center_rows[0])}

    # Fetch neighbors at the requested depth
    neighbor_rows: list[dict[str, Any]] = neo4j.execute_read(
        f"""
        MATCH (center:Narrator {{id: $id}})
        MATCH path = (center)-[:TRANSMITTED_TO*1..{depth}]-(neighbor:Narrator)
        WITH DISTINCT neighbor AS n
        RETURN {_NARRATOR_FIELDS.format(p="")}
        LIMIT $limit
        """,
        {"id": narrator_id, "limit": limit},
    )
    for r in neighbor_rows:
        nid = r["id"]
        if nid not in seen_nodes:
            seen_nodes[nid] = _row_to_graph_node(r)

    # Fetch all edges between the collected nodes
    node_ids = list(seen_nodes.keys())
    edge_rows: list[dict[str, Any]] = neo4j.execute_read(
        """
        MATCH (a:Narrator)-[r:TRANSMITTED_TO]->(b:Narrator)
        WHERE a.id IN $ids AND b.id IN $ids
        RETURN a.id AS source, b.id AS target, type(r) AS rel, count(r) AS weight
        """,
        {"ids": node_ids},
    )
    edges: list[GraphEdge] = [
        GraphEdge(
            source=r["source"],
            target=r["target"],
            relationship=r["rel"],
            weight=r.get("weight", 1),
        )
        for r in edge_rows
    ]

    # Also fetch STUDIED_UNDER edges
    studied_rows: list[dict[str, Any]] = neo4j.execute_read(
        """
        MATCH (a:Narrator)-[r:STUDIED_UNDER]->(b:Narrator)
        WHERE a.id IN $ids AND b.id IN $ids
        RETURN a.id AS source, b.id AS target, type(r) AS rel, count(r) AS weight
        """,
        {"ids": node_ids},
    )
    edges.extend(
        GraphEdge(
            source=r["source"],
            target=r["target"],
            relationship=r["rel"],
            weight=r.get("weight", 1),
        )
        for r in studied_rows
    )

    # Count direct teachers and students
    teacher_count = sum(
        1 for e in edges if e.target == narrator_id and e.relationship == "TRANSMITTED_TO"
    )
    student_count = sum(
        1 for e in edges if e.source == narrator_id and e.relationship == "TRANSMITTED_TO"
    )

    return NarratorNetworkResponse(
        narrator_id=narrator_id,
        nodes=list(seen_nodes.values()),
        edges=edges,
        teachers=teacher_count,
        students=student_count,
    )
