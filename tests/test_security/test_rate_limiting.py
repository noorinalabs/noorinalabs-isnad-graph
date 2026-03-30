"""SEC-05: Rate limiting validation tests.

Verifies that the RateLimitMiddleware enforces request limits per client IP,
using the in-memory fallback (no Redis in test environment).
Maps to OWASP OTG-BUSLOGIC-005.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware import RateLimitMiddleware


class TestRateLimitMiddleware:
    """Test the in-memory sliding-window rate limiter."""

    def _make_rate_limited_app(self, *, requests_per_minute: int = 5) -> FastAPI:
        """Create a minimal FastAPI app with rate limiting and mocked Neo4j."""
        from src.api.app import create_app

        app = create_app()
        mock_neo4j = MagicMock()
        mock_neo4j.execute_read.return_value = []
        mock_neo4j.execute_write.return_value = []
        app.state.neo4j = mock_neo4j

        # Add a stricter rate limiter on top of the existing one.
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=requests_per_minute,
            window_seconds=60,
            redis_url=None,
        )
        return app

    def test_requests_within_limit_succeed(self) -> None:
        """Requests within the per-minute limit should succeed."""
        app = self._make_rate_limited_app(requests_per_minute=10)
        client = TestClient(app, raise_server_exceptions=False)

        for _ in range(5):
            response = client.get("/health")
            assert response.status_code in (200, 503), (
                f"Expected 200/503 but got {response.status_code}"
            )

    def test_requests_exceeding_limit_return_429(self) -> None:
        """Requests exceeding the per-minute limit should return 429."""
        app = self._make_rate_limited_app(requests_per_minute=3)
        client = TestClient(app, raise_server_exceptions=False)

        statuses = []
        for _ in range(10):
            response = client.get("/health")
            statuses.append(response.status_code)

        # At least some requests should be rate-limited
        assert 429 in statuses, (
            f"Expected 429 in responses after exceeding limit, got {set(statuses)}"
        )

    def test_429_includes_retry_after_header(self) -> None:
        """Rate-limited responses must include a Retry-After header."""
        app = self._make_rate_limited_app(requests_per_minute=2)
        client = TestClient(app, raise_server_exceptions=False)

        for _ in range(5):
            response = client.get("/health")
            if response.status_code == 429:
                assert "Retry-After" in response.headers, (
                    "429 response must include Retry-After header"
                )
                break


class TestRateLimitMemoryFallback:
    """Test the in-memory sliding window directly."""

    def test_memory_check_allows_within_limit(self) -> None:
        """The _check_memory method should allow requests within limit."""
        mw = RateLimitMiddleware(app=MagicMock(), requests_per_minute=5, window_seconds=60)
        now = time.time()
        for i in range(5):
            assert mw._check_memory("127.0.0.1", now + i) is True

    def test_memory_check_blocks_over_limit(self) -> None:
        """The _check_memory method should block requests over the limit."""
        mw = RateLimitMiddleware(app=MagicMock(), requests_per_minute=3, window_seconds=60)
        now = time.time()
        for i in range(3):
            assert mw._check_memory("127.0.0.1", now + i) is True
        # 4th request should be blocked
        assert mw._check_memory("127.0.0.1", now + 3) is False

    def test_memory_window_expires(self) -> None:
        """Requests outside the sliding window should be allowed again."""
        mw = RateLimitMiddleware(app=MagicMock(), requests_per_minute=2, window_seconds=10)
        now = time.time()
        # Fill the window
        assert mw._check_memory("127.0.0.1", now) is True
        assert mw._check_memory("127.0.0.1", now + 1) is True
        assert mw._check_memory("127.0.0.1", now + 2) is False
        # After the window expires, should be allowed again
        assert mw._check_memory("127.0.0.1", now + 11) is True

    def test_separate_ips_have_separate_limits(self) -> None:
        """Rate limits are per-IP; different IPs have independent counters."""
        mw = RateLimitMiddleware(app=MagicMock(), requests_per_minute=2, window_seconds=60)
        now = time.time()
        # Fill IP A
        assert mw._check_memory("10.0.0.1", now) is True
        assert mw._check_memory("10.0.0.1", now + 1) is True
        assert mw._check_memory("10.0.0.1", now + 2) is False
        # IP B should still be allowed
        assert mw._check_memory("10.0.0.2", now + 2) is True
