"""Admin usage analytics endpoint."""

from __future__ import annotations

import time
from typing import Literal

import structlog
from fastapi import APIRouter, Depends, Query

from src.api.deps import get_neo4j
from src.api.models import PopularNarrator, UsageAnalyticsResponse
from src.utils.neo4j_client import Neo4jClient
from src.utils.redis_client import get_redis_client

router = APIRouter()

log = structlog.get_logger(logger_name=__name__)

# Redis key prefixes for analytics counters
_SEARCH_COUNTER_KEY = "analytics:search_count"
_API_CALL_COUNTER_KEY = "analytics:api_call_count"
_NARRATOR_QUERY_ZSET_KEY = "analytics:narrator_queries"

# Time-range lookback windows in seconds
_TIME_RANGE_SECONDS: dict[str, int] = {
    "1h": 3600,
    "24h": 86400,
    "7d": 604800,
    "30d": 2592000,
}


def _get_redis_counter(key: str, window_seconds: int) -> int:
    """Read a sliding-window counter from Redis.

    Returns 0 if Redis is unavailable or the key does not exist.
    """
    client = get_redis_client()
    if client is None:
        return 0
    try:
        now = time.time()
        window_start = now - window_seconds
        # Use sorted set with timestamps as scores for sliding window
        count: int = client.zcount(key, window_start, "+inf")
        return count
    except Exception:  # noqa: BLE001
        log.debug("redis_counter_read_failed", key=key)
        return 0


def _get_popular_narrators(neo4j: Neo4jClient, limit: int = 10) -> list[PopularNarrator]:
    """Fetch top narrators by query count from Redis, enriching names from Neo4j.

    Falls back to top narrators by in-degree from Neo4j if Redis is unavailable.
    """
    client = get_redis_client()

    # Try Redis first for query-count based popularity
    if client is not None:
        try:
            # zrevrange returns [(member, score), ...] with withscores=True
            top_entries = client.zrevrange(_NARRATOR_QUERY_ZSET_KEY, 0, limit - 1, withscores=True)
            if top_entries:
                narrators: list[PopularNarrator] = []
                for narrator_id, score in top_entries:
                    # Look up name from Neo4j
                    records = neo4j.execute_read(
                        "MATCH (n:NARRATOR {id: $nid}) RETURN n.name_en AS name",
                        {"nid": narrator_id},
                    )
                    name = records[0]["name"] if records else narrator_id
                    narrators.append(
                        PopularNarrator(
                            id=narrator_id,
                            name=name or narrator_id,
                            query_count=int(score),
                        )
                    )
                return narrators
        except Exception:  # noqa: BLE001
            log.debug("redis_popular_narrators_failed")

    # Fallback: top narrators by in-degree from Neo4j graph
    try:
        records = neo4j.execute_read(
            """
            MATCH (n:NARRATOR)<-[r:TRANSMITTED_TO]-()
            WITH n, count(r) AS degree
            ORDER BY degree DESC
            LIMIT $limit
            RETURN n.id AS id, n.name_en AS name, degree
            """,
            {"limit": limit},
        )
        return [
            PopularNarrator(
                id=r["id"],
                name=r["name"] or r["id"],
                query_count=r["degree"],
            )
            for r in records
        ]
    except Exception:  # noqa: BLE001
        log.debug("neo4j_popular_narrators_failed")
        return []


@router.get("/analytics", response_model=UsageAnalyticsResponse)
def usage_analytics(
    neo4j: Neo4jClient = Depends(get_neo4j),
    time_range: Literal["1h", "24h", "7d", "30d"] = Query("24h"),
) -> UsageAnalyticsResponse:
    """Return usage analytics: search volume, popular narrators, API call count.

    Reads real metrics from Redis counters and Neo4j graph data.  Degrades
    gracefully to zeros when metrics backends are unavailable.
    """
    window_seconds = _TIME_RANGE_SECONDS[time_range]

    search_volume = _get_redis_counter(_SEARCH_COUNTER_KEY, window_seconds)
    api_call_count = _get_redis_counter(_API_CALL_COUNTER_KEY, window_seconds)
    popular_narrators = _get_popular_narrators(neo4j)

    return UsageAnalyticsResponse(
        search_volume=search_volume,
        api_call_count=api_call_count,
        popular_narrators=popular_narrators,
    )
