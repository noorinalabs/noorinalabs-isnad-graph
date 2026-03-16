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
    """Return all isnad chains passing through a narrator."""
    # Verify narrator exists
    exists = neo4j.execute_read(
        "MATCH (n:Narrator {id: $id}) RETURN n.id AS id",
        {"id": narrator_id},
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Narrator '{narrator_id}' not found")

    rows = neo4j.execute_read(
        """
        MATCH (n:Narrator {id: $id})<-[:HAS_LINK]-(c:Chain)-[:CHAIN_OF]->(h:Hadith)
        RETURN c.id AS chain_id, h.id AS hadith_id, h.matn_ar AS matn_ar,
               h.matn_en AS matn_en, h.grade_composite AS grade
        ORDER BY c.id
        LIMIT $limit
        """,
        {"id": narrator_id, "limit": limit},
    )
    chains = [
        ChainSummary(
            chain_id=r["chain_id"],
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
    """Return full chain visualization data for a hadith (nodes + edges for D3/vis.js)."""
    exists = neo4j.execute_read(
        "MATCH (h:Hadith {id: $id}) RETURN h.id AS id",
        {"id": hadith_id},
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Hadith '{hadith_id}' not found")

    rows = neo4j.execute_read(
        """
        MATCH (h:Hadith {id: $id})<-[:CHAIN_OF]-(c:Chain)-[:HAS_LINK]->(n:Narrator)
        WITH c, collect(n) AS narrators
        MATCH (c)-[:HAS_LINK]->(src:Narrator)-[:TRANSMITTED_TO]->(tgt:Narrator)
        WHERE src IN narrators AND tgt IN narrators
        RETURN c.id AS chain_id,
               src.id AS source_id, src.name_ar AS source_name_ar,
               src.name_en AS source_name_en, src.generation AS source_gen,
               tgt.id AS target_id, tgt.name_ar AS target_name_ar,
               tgt.name_en AS target_name_en, tgt.generation AS target_gen
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
            )
        )

    return ChainVisualization(
        hadith_id=hadith_id,
        nodes=list(seen_nodes.values()),
        edges=edges,
    )


@router.get(
    "/graph/narrator/{narrator_id}/network",
    response_model=NarratorNetworkResponse,
)
def get_narrator_network(
    narrator_id: str,
    limit: int = Query(50, ge=1, le=200),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> NarratorNetworkResponse:
    """Return ego network: direct teachers and students of a narrator."""
    exists = neo4j.execute_read(
        "MATCH (n:Narrator {id: $id}) RETURN n.id AS id",
        {"id": narrator_id},
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Narrator '{narrator_id}' not found")

    rows: list[dict[str, Any]] = neo4j.execute_read(
        """
        MATCH (center:Narrator {id: $id})
        OPTIONAL MATCH (center)-[r1:TRANSMITTED_TO]->(student:Narrator)
        WITH center, collect(DISTINCT {id: student.id, name_ar: student.name_ar,
             name_en: student.name_en, gen: student.generation, rel: 'student'}) AS students
        OPTIONAL MATCH (teacher:Narrator)-[r2:TRANSMITTED_TO]->(center)
        WITH center, students,
             collect(DISTINCT {id: teacher.id, name_ar: teacher.name_ar,
             name_en: teacher.name_en, gen: teacher.generation, rel: 'teacher'}) AS teachers
        RETURN center.name_ar AS center_name_ar, center.name_en AS center_name_en,
               center.generation AS center_gen,
               students[0..$limit] AS students, teachers[0..$limit] AS teachers
        """,
        {"id": narrator_id, "limit": limit},
    )

    if not rows:
        return NarratorNetworkResponse(
            narrator_id=narrator_id, nodes=[], edges=[], teachers=0, students=0
        )

    row = rows[0]
    seen_nodes: dict[str, GraphNode] = {
        narrator_id: GraphNode(
            id=narrator_id,
            label=row.get("center_name_en") or row["center_name_ar"],
            name_ar=row["center_name_ar"],
            name_en=row.get("center_name_en"),
            type="narrator",
            generation=row.get("center_gen"),
        )
    }
    edges: list[GraphEdge] = []
    teacher_count = 0
    student_count = 0

    for t in row.get("teachers") or []:
        if t.get("id") is None:
            continue
        teacher_count += 1
        if t["id"] not in seen_nodes:
            seen_nodes[t["id"]] = GraphNode(
                id=t["id"],
                label=t.get("name_en") or t["name_ar"],
                name_ar=t["name_ar"],
                name_en=t.get("name_en"),
                type="narrator",
                generation=t.get("gen"),
            )
        edges.append(GraphEdge(source=t["id"], target=narrator_id, relationship="TRANSMITTED_TO"))

    for s in row.get("students") or []:
        if s.get("id") is None:
            continue
        student_count += 1
        if s["id"] not in seen_nodes:
            seen_nodes[s["id"]] = GraphNode(
                id=s["id"],
                label=s.get("name_en") or s["name_ar"],
                name_ar=s["name_ar"],
                name_en=s.get("name_en"),
                type="narrator",
                generation=s.get("gen"),
            )
        edges.append(GraphEdge(source=narrator_id, target=s["id"], relationship="TRANSMITTED_TO"))

    return NarratorNetworkResponse(
        narrator_id=narrator_id,
        nodes=list(seen_nodes.values()),
        edges=edges,
        teachers=teacher_count,
        students=student_count,
    )
