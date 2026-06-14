"""Admin content statistics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_neo4j
from src.api.models import CollectionStat, ContentStatsResponse, SectStat
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()

_AGGREGATE_QUERY = """
    OPTIONAL MATCH (h:Hadith) WITH count(h) AS hadith_count
    OPTIONAL MATCH (n:Narrator) WITH hadith_count, count(n) AS narrator_count
    OPTIONAL MATCH (c:Collection)
    WITH hadith_count, narrator_count, count(c) AS collection_count
    OPTIONAL MATCH (h2:Hadith)-[:APPEARS_IN]->(:Collection)
    WITH hadith_count, narrator_count, collection_count,
         count(DISTINCT h2) AS linked_hadiths
    RETURN hadith_count, narrator_count, collection_count,
           CASE WHEN hadith_count > 0
                THEN toFloat(linked_hadiths) / toFloat(hadith_count) * 100.0
                ELSE 0.0 END AS coverage_pct
"""

# Per-collection hadith counts, used to surface corpus *scope* (which
# collections / sects are actually loaded) so the totals are not read as a
# complete corpus. Hadith are counted via APPEARS_IN; a collection with no
# linked hadith still appears with a zero count.
_BREAKDOWN_QUERY = """
    MATCH (c:Collection)
    OPTIONAL MATCH (h:Hadith)-[:APPEARS_IN]->(c)
    RETURN c.id AS id,
           coalesce(c.name_en, c.name_ar, c.id) AS name,
           coalesce(c.sect, 'unknown') AS sect,
           count(h) AS hadith_count
    ORDER BY hadith_count DESC, name ASC
"""


def _collection_breakdown(neo4j: Neo4jClient) -> list[CollectionStat]:
    """Return the per-collection hadith counts (empty when Neo4j is empty/down)."""
    records = neo4j.execute_read(_BREAKDOWN_QUERY)
    return [
        CollectionStat(
            id=r.get("id") or "",
            name=r.get("name") or (r.get("id") or ""),
            sect=r.get("sect") or "unknown",
            hadith_count=r.get("hadith_count", 0) or 0,
        )
        for r in records
        # Skip rows with no identity at all (defensive against null Collection ids).
        if r.get("id") or r.get("name")
    ]


def _sect_breakdown(collections: list[CollectionStat]) -> list[SectStat]:
    """Aggregate per-collection counts into per-sect totals."""
    totals: dict[str, list[int]] = {}
    for c in collections:
        bucket = totals.setdefault(c.sect, [0, 0])
        bucket[0] += c.hadith_count
        bucket[1] += 1
    return [
        SectStat(sect=sect, hadith_count=hadith_count, collection_count=collection_count)
        for sect, (hadith_count, collection_count) in sorted(
            totals.items(), key=lambda kv: kv[1][0], reverse=True
        )
    ]


@router.get("/stats", response_model=ContentStatsResponse)
def content_stats(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> ContentStatsResponse:
    """Return content statistics plus a corpus-scope breakdown.

    The top-level counts (hadith / narrator / collection / coverage) report the
    loaded graph as-is; ``collections`` and ``sects`` describe *what* that data
    is so the totals are not mistaken for a complete corpus. See
    ``ContentStatsResponse`` for the ``narrator_count`` caveat.
    """
    records = neo4j.execute_read(_AGGREGATE_QUERY)
    collections = _collection_breakdown(neo4j)
    sects = _sect_breakdown(collections)

    if records:
        r = records[0]
        return ContentStatsResponse(
            hadith_count=r.get("hadith_count", 0),
            narrator_count=r.get("narrator_count", 0),
            collection_count=r.get("collection_count", 0),
            coverage_pct=round(r.get("coverage_pct", 0.0), 2),
            collections=collections,
            sects=sects,
        )

    return ContentStatsResponse(
        hadith_count=0,
        narrator_count=0,
        collection_count=0,
        coverage_pct=0.0,
        collections=collections,
        sects=sects,
    )
