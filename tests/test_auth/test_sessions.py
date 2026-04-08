"""Tests for server-side session management (#728)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from src.auth.sessions import (
    _sessions,
    create_session,
    destroy_all_user_sessions,
    destroy_session,
    get_idle_timeout_warning_seconds,
    get_session,
    list_user_sessions,
    touch_session,
)


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    """Clear in-memory session store between tests."""
    _sessions.clear()


class TestCreateSession:
    def test_creates_session_and_returns_id(self) -> None:
        sid = create_session("user-1", "127.0.0.1", "Mozilla/5.0", role="viewer")
        assert isinstance(sid, str)
        assert len(sid) == 64  # 32 hex bytes

    def test_session_is_retrievable(self) -> None:
        sid = create_session("user-1", "10.0.0.1", "Chrome/120", role="editor")
        session = get_session(sid)
        assert session is not None
        assert session.user_id == "user-1"
        assert session.ip_address == "10.0.0.1"
        assert session.user_agent == "Chrome/120"
        assert session.role == "editor"

    def test_concurrent_limit_evicts_oldest(self) -> None:
        # With max_concurrent_sessions=5, creating 6 should evict the first
        sids = []
        for i in range(6):
            sid = create_session("user-1", f"10.0.0.{i}", f"Agent-{i}")
            sids.append(sid)

        # First session should be evicted
        assert get_session(sids[0]) is None
        # Last 5 should remain
        for sid in sids[1:]:
            assert get_session(sid) is not None

    def test_sessions_for_different_users_independent(self) -> None:
        sid1 = create_session("user-1", "10.0.0.1", "Agent-1")
        sid2 = create_session("user-2", "10.0.0.2", "Agent-2")
        assert get_session(sid1) is not None
        assert get_session(sid2) is not None


class TestGetSession:
    def test_returns_none_for_unknown_id(self) -> None:
        assert get_session("nonexistent") is None

    def test_returns_none_for_expired_session(self) -> None:
        sid = create_session("user-1", "10.0.0.1", "Agent")
        # Manually set last_active far in the past
        _sessions[sid]["last_active"] = str(time.time() - 7200)  # 2 hours ago
        assert get_session(sid) is None


class TestTouchSession:
    def test_refreshes_last_active(self) -> None:
        sid = create_session("user-1", "10.0.0.1", "Agent")
        session_before = get_session(sid)
        assert session_before is not None
        original_last_active = session_before.last_active

        time.sleep(0.01)
        assert touch_session(sid) is True

        session_after = get_session(sid)
        assert session_after is not None
        assert session_after.last_active >= original_last_active

    def test_returns_false_for_unknown_session(self) -> None:
        assert touch_session("nonexistent") is False

    def test_returns_false_for_expired_session(self) -> None:
        sid = create_session("user-1", "10.0.0.1", "Agent")
        _sessions[sid]["last_active"] = str(time.time() - 7200)
        assert touch_session(sid) is False


class TestDestroySession:
    def test_removes_session(self) -> None:
        sid = create_session("user-1", "10.0.0.1", "Agent")
        assert get_session(sid) is not None
        destroy_session(sid)
        assert get_session(sid) is None

    def test_noop_for_unknown_session(self) -> None:
        destroy_session("nonexistent")  # Should not raise


class TestDestroyAllUserSessions:
    def test_removes_all_sessions_for_user(self) -> None:
        sid1 = create_session("user-1", "10.0.0.1", "Agent-1")
        sid2 = create_session("user-1", "10.0.0.2", "Agent-2")
        sid3 = create_session("user-2", "10.0.0.3", "Agent-3")

        count = destroy_all_user_sessions("user-1")
        assert count == 2
        assert get_session(sid1) is None
        assert get_session(sid2) is None
        assert get_session(sid3) is not None  # Other user unaffected

    def test_returns_zero_for_unknown_user(self) -> None:
        assert destroy_all_user_sessions("nobody") == 0


class TestListUserSessions:
    def test_lists_all_active_sessions(self) -> None:
        create_session("user-1", "10.0.0.1", "Agent-1")
        create_session("user-1", "10.0.0.2", "Agent-2")
        create_session("user-2", "10.0.0.3", "Agent-3")

        sessions = list_user_sessions("user-1")
        assert len(sessions) == 2
        ips = {s.ip_address for s in sessions}
        assert ips == {"10.0.0.1", "10.0.0.2"}

    def test_empty_for_unknown_user(self) -> None:
        assert list_user_sessions("nobody") == []


class TestIdleTimeoutWarning:
    def test_returns_configured_value(self) -> None:
        seconds = get_idle_timeout_warning_seconds()
        assert seconds == 60  # Default from settings


class TestRedisIntegration:
    """Test Redis-backed session operations."""

    def test_create_session_uses_redis_when_available(self) -> None:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.zcard.return_value = 0

        pipe = MagicMock()
        mock_redis.pipeline.return_value = pipe
        pipe.execute.return_value = [True, True, True, True]

        with patch("src.auth.sessions.get_redis_client", return_value=mock_redis):
            sid = create_session("user-redis", "10.0.0.1", "Agent", role="admin")

        assert isinstance(sid, str)
        pipe.hset.assert_called_once()
        pipe.expire.assert_called()

    def test_falls_back_to_memory_on_redis_error(self) -> None:
        import redis as redis_lib

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.pipeline.side_effect = redis_lib.ConnectionError("down")

        with patch("src.auth.sessions.get_redis_client", return_value=mock_redis):
            sid = create_session("user-fallback", "10.0.0.1", "Agent")

        # Should still succeed via in-memory fallback
        assert sid in _sessions
