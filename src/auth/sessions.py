"""Server-side session management with Redis/in-memory fallback.

Provides idle timeout, concurrent session limits, and session
invalidation on role change. Sessions are tracked in Redis with
metadata (device info, IP, last active timestamp).
"""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any

import redis as redis_lib

from src.config import AuthSettings, get_settings
from src.utils.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# In-memory fallback for when Redis is unavailable
_sessions: dict[str, dict[str, str]] = {}


@dataclass(frozen=True)
class SessionInfo:
    """Metadata for an active session."""

    session_id: str
    user_id: str
    ip_address: str
    user_agent: str
    created_at: float
    last_active: float
    role: str | None = None


def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


def _user_sessions_key(user_id: str) -> str:
    return f"user_sessions:{user_id}"


def create_session(
    user_id: str,
    ip_address: str,
    user_agent: str,
    role: str | None = None,
) -> str:
    """Create a new server-side session and return the session ID.

    Enforces the concurrent session limit: if the user already has the
    maximum number of sessions, the oldest session is evicted.
    """
    settings = get_settings().auth
    session_id = secrets.token_hex(32)
    now = time.time()

    session_data: dict[str, str] = {
        "user_id": user_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "created_at": str(now),
        "last_active": str(now),
        "role": role or "",
    }

    redis_client = get_redis_client()
    if redis_client is not None:
        try:
            _create_session_redis(redis_client, session_id, user_id, session_data, settings, now)
            return session_id
        except (redis_lib.ConnectionError, redis_lib.TimeoutError, OSError):
            logger.warning("Redis session create failed, falling back to in-memory")

    _create_session_memory(session_id, user_id, session_data, settings, now)
    return session_id


def _create_session_redis(
    client: Any,
    session_id: str,
    user_id: str,
    data: dict[str, str],
    settings: AuthSettings,
    now: float,
) -> None:
    """Create session in Redis with concurrent session enforcement."""
    max_sessions = settings.max_concurrent_sessions
    idle_timeout = settings.session_idle_timeout_minutes * 60
    key = _session_key(session_id)
    user_key = _user_sessions_key(user_id)

    pipe = client.pipeline()
    pipe.hset(key, mapping=data)
    pipe.expire(key, idle_timeout)
    pipe.zadd(user_key, {session_id: now})
    pipe.expire(user_key, idle_timeout + 3600)
    pipe.execute()

    # Enforce concurrent session limit
    _enforce_limit_redis(client, user_id, max_sessions)


def _enforce_limit_redis(
    client: Any,
    user_id: str,
    max_sessions: int,
) -> None:
    """Evict oldest sessions if user exceeds the limit."""
    if max_sessions <= 0:
        return
    user_key = _user_sessions_key(user_id)
    count: int = client.zcard(user_key)
    if count > max_sessions:
        excess = count - max_sessions
        oldest: list[str] = client.zrange(user_key, 0, excess - 1)
        pipe = client.pipeline()
        for sid in oldest:
            pipe.delete(_session_key(sid))
            pipe.zrem(user_key, sid)
        pipe.execute()


def _create_session_memory(
    session_id: str,
    user_id: str,
    data: dict[str, str],
    settings: AuthSettings,
    now: float,
) -> None:
    """Create session in in-memory store with concurrent session enforcement."""
    max_sessions = settings.max_concurrent_sessions
    _sessions[session_id] = {**data, "session_id": session_id}

    # Enforce concurrent session limit
    user_sessions = [
        (sid, sdata) for sid, sdata in _sessions.items() if sdata.get("user_id") == user_id
    ]
    if max_sessions > 0 and len(user_sessions) > max_sessions:
        user_sessions.sort(key=lambda x: float(x[1].get("created_at", "0")))
        excess = len(user_sessions) - max_sessions
        for sid, _ in user_sessions[:excess]:
            _sessions.pop(sid, None)


def get_session(session_id: str) -> SessionInfo | None:
    """Retrieve session metadata. Returns None if expired or not found."""
    redis_client = get_redis_client()
    if redis_client is not None:
        try:
            return _get_session_redis(redis_client, session_id)
        except (redis_lib.ConnectionError, redis_lib.TimeoutError, OSError):
            logger.warning("Redis session get failed, falling back to in-memory")

    return _get_session_memory(session_id)


def _get_session_redis(client: Any, session_id: str) -> SessionInfo | None:
    key = _session_key(session_id)
    data: dict[str, str] = client.hgetall(key)
    if not data:
        return None
    return SessionInfo(
        session_id=session_id,
        user_id=data.get("user_id", ""),
        ip_address=data.get("ip_address", ""),
        user_agent=data.get("user_agent", ""),
        created_at=float(data.get("created_at", "0")),
        last_active=float(data.get("last_active", "0")),
        role=data.get("role") or None,
    )


def _get_session_memory(session_id: str) -> SessionInfo | None:
    settings = get_settings().auth
    data = _sessions.get(session_id)
    if data is None:
        return None
    idle_timeout = settings.session_idle_timeout_minutes * 60
    last_active = float(data.get("last_active", "0"))
    if time.time() - last_active > idle_timeout:
        _sessions.pop(session_id, None)
        return None
    return SessionInfo(
        session_id=session_id,
        user_id=data.get("user_id", ""),
        ip_address=data.get("ip_address", ""),
        user_agent=data.get("user_agent", ""),
        created_at=float(data.get("created_at", "0")),
        last_active=last_active,
        role=data.get("role") or None,
    )


def touch_session(session_id: str) -> bool:
    """Update the last_active timestamp for a session (heartbeat).

    Returns True if the session exists and was refreshed, False if
    the session has expired or does not exist.
    """
    settings = get_settings().auth
    idle_timeout = settings.session_idle_timeout_minutes * 60
    now = time.time()

    redis_client = get_redis_client()
    if redis_client is not None:
        try:
            return _touch_session_redis(redis_client, session_id, idle_timeout, now)
        except (redis_lib.ConnectionError, redis_lib.TimeoutError, OSError):
            logger.warning("Redis session touch failed, falling back to in-memory")

    return _touch_session_memory(session_id, idle_timeout, now)


def _touch_session_redis(client: Any, session_id: str, idle_timeout: int, now: float) -> bool:
    key = _session_key(session_id)
    if not client.exists(key):
        return False
    pipe = client.pipeline()
    pipe.hset(key, "last_active", str(now))
    pipe.expire(key, idle_timeout)
    pipe.execute()
    return True


def _touch_session_memory(session_id: str, idle_timeout: int, now: float) -> bool:
    data = _sessions.get(session_id)
    if data is None:
        return False
    last_active = float(data.get("last_active", "0"))
    if now - last_active > idle_timeout:
        _sessions.pop(session_id, None)
        return False
    data["last_active"] = str(now)
    return True


def destroy_session(session_id: str) -> None:
    """Destroy a specific session."""
    redis_client = get_redis_client()
    if redis_client is not None:
        try:
            _destroy_session_redis(redis_client, session_id)
            return
        except (redis_lib.ConnectionError, redis_lib.TimeoutError, OSError):
            logger.warning("Redis session destroy failed, falling back to in-memory")

    _sessions.pop(session_id, None)


def _destroy_session_redis(client: Any, session_id: str) -> None:
    key = _session_key(session_id)
    data: dict[str, str] = client.hgetall(key)
    user_id = data.get("user_id", "") if data else ""
    pipe = client.pipeline()
    pipe.delete(key)
    if user_id:
        pipe.zrem(_user_sessions_key(user_id), session_id)
    pipe.execute()


def destroy_all_user_sessions(user_id: str) -> int:
    """Destroy all sessions for a user. Returns the count of sessions destroyed."""
    redis_client = get_redis_client()
    if redis_client is not None:
        try:
            return _destroy_all_redis(redis_client, user_id)
        except (redis_lib.ConnectionError, redis_lib.TimeoutError, OSError):
            logger.warning("Redis destroy-all failed, falling back to in-memory")

    return _destroy_all_memory(user_id)


def _destroy_all_redis(client: Any, user_id: str) -> int:
    user_key = _user_sessions_key(user_id)
    session_ids: list[str] = client.zrange(user_key, 0, -1)
    if not session_ids:
        return 0
    pipe = client.pipeline()
    for sid in session_ids:
        pipe.delete(_session_key(sid))
    pipe.delete(user_key)
    pipe.execute()
    return len(session_ids)


def _destroy_all_memory(user_id: str) -> int:
    to_remove = [sid for sid, data in _sessions.items() if data.get("user_id") == user_id]
    for sid in to_remove:
        _sessions.pop(sid, None)
    return len(to_remove)


def list_user_sessions(user_id: str) -> list[SessionInfo]:
    """List all active sessions for a user."""
    redis_client = get_redis_client()
    if redis_client is not None:
        try:
            return _list_sessions_redis(redis_client, user_id)
        except (redis_lib.ConnectionError, redis_lib.TimeoutError, OSError):
            logger.warning("Redis list sessions failed, falling back to in-memory")

    return _list_sessions_memory(user_id)


def _list_sessions_redis(client: Any, user_id: str) -> list[SessionInfo]:
    user_key = _user_sessions_key(user_id)
    session_ids: list[str] = client.zrange(user_key, 0, -1)
    sessions: list[SessionInfo] = []
    for sid in session_ids:
        info = _get_session_redis(client, sid)
        if info is not None:
            sessions.append(info)
        else:
            # Clean up stale reference
            client.zrem(user_key, sid)
    return sessions


def _list_sessions_memory(user_id: str) -> list[SessionInfo]:
    sessions: list[SessionInfo] = []
    for sid, data in list(_sessions.items()):
        if data.get("user_id") == user_id:
            info = _get_session_memory(sid)
            if info is not None:
                sessions.append(info)
    return sessions


def get_idle_timeout_warning_seconds() -> int:
    """Return the number of seconds before idle timeout to show a warning."""
    settings = get_settings().auth
    return settings.session_idle_warning_seconds
