"""Parallel hadith endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_neo4j
from src.api.models import (
    ParallelHadithResponse,
    ParallelPair,
    ParallelPairsResponse,
    ParallelsResponse,
)
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


@router.get("/parallels", response_model=ParallelPairsResponse)
def list_parallels(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100),
    cross_sect: bool | None = Query(
        None,
        description=(
            "Optional facet. Omit to span both sects (intra-sunni, intra-shia, AND "
            "cross-sect); pass true for cross-sect only, false for intra-sect only."
        ),
    ),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> ParallelPairsResponse:
    """Return paginated list of parallel hadith pairs with similarity scores.

    Spans every sect combination by default — sunni-sunni, shia-shia, and
    sunni-shia. ``cross_sect`` is an optional facet, not a mandatory filter.
    """
    where = "WHERE r.cross_sect = $cross_sect" if cross_sect is not None else ""
    filter_params: dict[str, Any] = {} if cross_sect is None else {"cross_sect": cross_sect}

    count_rows = neo4j.execute_read(
        f"MATCH (:Hadith)-[r:PARALLEL_OF]->(:Hadith) {where} RETURN count(r) AS total",
        filter_params,
    )
    total = count_rows[0]["total"] if count_rows else 0

    skip = (page - 1) * limit
    rows = neo4j.execute_read(
        f"""
        MATCH (a:Hadith)-[r:PARALLEL_OF]->(b:Hadith)
        {where}
        RETURN a.id AS a_id, a.source_corpus AS a_corpus,
               b.id AS b_id, b.source_corpus AS b_corpus,
               r.similarity_score AS similarity_score,
               r.variant_type AS variant_type,
               r.cross_sect AS cross_sect
        ORDER BY r.similarity_score DESC
        SKIP $skip
        LIMIT $limit
        """,
        {**filter_params, "skip": skip, "limit": limit},
    )

    items = [
        ParallelPair(
            hadith_a_id=r["a_id"],
            hadith_a_corpus=r.get("a_corpus", ""),
            hadith_b_id=r["b_id"],
            hadith_b_corpus=r.get("b_corpus", ""),
            similarity_score=r.get("similarity_score"),
            variant_type=r.get("variant_type"),
            cross_sect=bool(r.get("cross_sect", False)),
        )
        for r in rows
    ]
    return ParallelPairsResponse(items=items, total=total, page=page, limit=limit)


@router.get("/parallels/{hadith_id}", response_model=ParallelsResponse)
def get_parallels(
    hadith_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100),
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> ParallelsResponse:
    """Return parallel hadiths via PARALLEL_OF relationships."""
    exists = neo4j.execute_read(
        "MATCH (h:Hadith {id: $id}) RETURN h.id AS id",
        {"id": hadith_id},
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"Hadith '{hadith_id}' not found")

    skip = (page - 1) * limit

    rows = neo4j.execute_read(
        """
        MATCH (h:Hadith {id: $id})-[r:PARALLEL_OF]-(p:Hadith)
        RETURN p.id AS id, p.matn_ar AS matn_ar, p.matn_en AS matn_en,
               p.source_corpus AS source_corpus, p.grade_composite AS grade,
               r.similarity_score AS similarity_score,
               r.variant_type AS variant_type,
               r.cross_sect AS cross_sect
        ORDER BY r.similarity_score DESC
        SKIP $skip
        LIMIT $limit
        """,
        {"id": hadith_id, "skip": skip, "limit": limit},
    )

    parallels = [
        ParallelHadithResponse(
            id=r["id"],
            matn_ar=r["matn_ar"],
            matn_en=r.get("matn_en"),
            source_corpus=r.get("source_corpus", ""),
            grade=r.get("grade"),
            similarity_score=r.get("similarity_score"),
            variant_type=r.get("variant_type"),
            cross_sect=bool(r.get("cross_sect", False)),
        )
        for r in rows
    ]
    return ParallelsResponse(hadith_id=hadith_id, parallels=parallels, total=len(parallels))
