"""Shared Redis client helper with graceful fallback."""

from __future__ import annotations

import logging
from typing import Any

from src.config import get_settings

logger = logging.getLogger(__name__)


def get_redis_client() -> Any | None:
    """Return a Redis client or None if unavailable.

    Attempts to connect and ping Redis. Returns None on connection
    failure so callers can fall back to in-memory alternatives.
    """
    try:
        import redis

        settings = get_settings().redis
        client = redis.Redis.from_url(settings.url, decode_responses=True)
        client.ping()
        return client
    except Exception:  # noqa: BLE001
        return None
