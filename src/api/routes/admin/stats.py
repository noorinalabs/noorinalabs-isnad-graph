"""Admin content statistics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.deps import get_neo4j
from src.api.models import ContentStatsResponse
from src.utils.neo4j_client import Neo4jClient

router = APIRouter()


@router.get("/stats", response_model=ContentStatsResponse)
def content_stats(
    neo4j: Neo4jClient = Depends(get_neo4j),
) -> ContentStatsResponse:
    """Return content statistics: hadith count, narrator count, collection count, coverage %."""
    query = """
        OPTIONAL MATCH (h:HADITH) WITH count(h) AS hadith_count
        OPTIONAL MATCH (n:NARRATOR) WITH hadith_count, count(n) AS narrator_count
        OPTIONAL MATCH (c:COLLECTION)
        WITH hadith_count, narrator_count, count(c) AS collection_count
        OPTIONAL MATCH (h2:HADITH)-[:APPEARS_IN]->(:COLLECTION)
        WITH hadith_count, narrator_count, collection_count,
             count(DISTINCT h2) AS linked_hadiths
        RETURN hadith_count, narrator_count, collection_count,
               CASE WHEN hadith_count > 0
                    THEN toFloat(linked_hadiths) / toFloat(hadith_count) * 100.0
                    ELSE 0.0 END AS coverage_pct
    """
    records = neo4j.execute_read(query)

    if records:
        r = records[0]
        return ContentStatsResponse(
            hadith_count=r.get("hadith_count", 0),
            narrator_count=r.get("narrator_count", 0),
            collection_count=r.get("collection_count", 0),
            coverage_pct=round(r.get("coverage_pct", 0.0), 2),
        )

    return ContentStatsResponse(
        hadith_count=0, narrator_count=0, collection_count=0, coverage_pct=0.0
    )
