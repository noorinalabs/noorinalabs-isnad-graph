"""Tests for security headers, rate limiting, input validation, and 2FA stubs."""

from __future__ import annotations

import os
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _clean_settings_cache() -> None:
    """Clear get_settings cache before each test so env changes take effect."""
    get_settings.cache_clear()


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Test settings with safe defaults, env vars cleared to avoid .env conflicts."""
    monkeypatch.delenv("PG_DSN", raising=False)
    for key in list(os.environ):
        if key.startswith(("NEO4J_", "PG_", "REDIS_")):
            monkeypatch.delenv(key, raising=False)
    return Settings(_env_file=None)


@pytest.fixture(autouse=True)
def _patch_settings(test_settings: Settings) -> Iterator[None]:
    """Patch get_settings globally for all security tests."""
    with patch("src.config.get_settings", return_value=test_settings):
        yield


@pytest.fixture
def mock_neo4j() -> MagicMock:
    """Mock Neo4jClient for API tests."""
    client = MagicMock()
    client.execute_read.return_value = []
    client.execute_write.return_value = []
    return client


@pytest.fixture
def app(mock_neo4j: MagicMock):  # noqa: ANN201
    """FastAPI app with mocked Neo4j (lifespan disabled)."""
    from datetime import UTC, datetime

    from fastapi import FastAPI

    from src.api.app import create_app
    from src.api.middleware import require_auth
    from src.auth.models import User

    app: FastAPI = create_app()
    app.state.neo4j = mock_neo4j
    app.dependency_overrides[require_auth] = lambda: User(
        id="test-user",
        email="test@example.com",
        name="Test User",
        provider="jwt",
        provider_user_id="test-user",
        created_at=datetime.now(UTC),
    )
    return app


@pytest.fixture
def client(app):  # noqa: ANN001, ANN201
    """Test client."""
    return TestClient(app)


# --- Security Headers ---


class TestSecurityHeaders:
    """Verify OWASP-recommended security headers are present on all responses."""

    def test_x_content_type_options(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_x_xss_protection(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.headers.get("x-xss-protection") == "1; mode=block"

    def test_strict_transport_security(self, client: TestClient) -> None:
        resp = client.get("/health")
        hsts = resp.headers.get("strict-transport-security", "")
        assert "max-age=" in hsts
        assert "includeSubDomains" in hsts

    def test_content_security_policy(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.headers.get("content-security-policy") == "default-src 'self'"

    def test_referrer_policy(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert "camera=()" in resp.headers.get("permissions-policy", "")

    def test_headers_on_api_endpoint(self, client: TestClient) -> None:
        """Security headers should be present on API routes too."""
        resp = client.get("/api/v1/narrators")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"


# --- Rate Limiting ---


class TestRateLimiting:
    """Verify rate limiting middleware rejects excessive requests."""

    def test_rate_limit_returns_429(self) -> None:
        """After exceeding the limit, subsequent requests get 429."""
        from fastapi import FastAPI as FA

        from src.api.middleware import RateLimitMiddleware

        mini = FA()

        @mini.get("/test")
        def _test_endpoint() -> dict[str, str]:
            return {"ok": "true"}

        mini.add_middleware(RateLimitMiddleware, requests_per_minute=3)
        tc = TestClient(mini)

        for _ in range(3):
            r = tc.get("/test")
            assert r.status_code == 200

        r = tc.get("/test")
        assert r.status_code == 429
        assert "retry-after" in r.headers


# --- Request Size Limits ---


class TestRequestSizeLimits:
    """Verify request body size limits."""

    def test_oversized_request_rejected(self) -> None:
        """Requests exceeding the body size limit get 413."""
        from fastapi import FastAPI as FA

        from src.api.middleware import RequestSizeLimitMiddleware

        mini = FA()

        @mini.post("/upload")
        async def _upload() -> dict[str, str]:
            return {"ok": "true"}

        mini.add_middleware(RequestSizeLimitMiddleware, max_body_size=100)
        tc = TestClient(mini)

        # Small request should pass
        resp = tc.post("/upload", content=b"small")
        assert resp.status_code == 200

        # Large request should be rejected
        resp = tc.post("/upload", content=b"x" * 200, headers={"content-length": "200"})
        assert resp.status_code == 413


# --- Input Validation ---


class TestInputValidation:
    """Verify Pydantic field constraints reject bad input."""

    def test_narrators_page_negative(self, client: TestClient) -> None:
        resp = client.get("/api/v1/narrators?page=-1")
        assert resp.status_code == 422

    def test_narrators_page_zero(self, client: TestClient) -> None:
        resp = client.get("/api/v1/narrators?page=0")
        assert resp.status_code == 422

    def test_narrators_limit_too_high(self, client: TestClient) -> None:
        resp = client.get("/api/v1/narrators?limit=999")
        assert resp.status_code == 422

    def test_narrators_limit_zero(self, client: TestClient) -> None:
        resp = client.get("/api/v1/narrators?limit=0")
        assert resp.status_code == 422

    def test_hadiths_page_negative(self, client: TestClient) -> None:
        resp = client.get("/api/v1/hadiths?page=-1")
        assert resp.status_code == 422

    def test_hadiths_limit_too_high(self, client: TestClient) -> None:
        resp = client.get("/api/v1/hadiths?limit=999")
        assert resp.status_code == 422

    def test_search_empty_query(self, client: TestClient) -> None:
        resp = client.get("/api/v1/search?q=")
        assert resp.status_code == 422

    def test_collections_limit_too_high(self, client: TestClient) -> None:
        resp = client.get("/api/v1/collections?limit=999")
        assert resp.status_code == 422

    def test_timeline_limit_too_high(self, client: TestClient) -> None:
        resp = client.get("/api/v1/timeline?limit=999")
        assert resp.status_code == 422

    def test_graph_network_limit_too_high(self, client: TestClient) -> None:
        resp = client.get("/api/v1/graph/narrator/test/network?limit=999")
        assert resp.status_code == 422


# --- 2FA Stub Endpoints ---


class TestTwoFAStubs:
    """Verify 2FA endpoints return 501 Not Implemented."""

    def test_enroll_returns_501(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/2fa/enroll")
        assert resp.status_code == 501
        assert "not yet implemented" in resp.json()["detail"].lower()

    def test_verify_returns_501(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/2fa/verify")
        assert resp.status_code == 501
        assert "not yet implemented" in resp.json()["detail"].lower()

    def test_recovery_returns_501(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/2fa/recovery")
        assert resp.status_code == 501
        assert "not yet implemented" in resp.json()["detail"].lower()


# --- ID Sanitization ---


class TestSanitizeId:
    """Verify ID sanitization utility."""

    def test_valid_id(self) -> None:
        from src.api.security import sanitize_id

        assert sanitize_id("nar-001") == "nar-001"

    def test_valid_id_with_dots(self) -> None:
        from src.api.security import sanitize_id

        assert sanitize_id("col.bukhari.1") == "col.bukhari.1"

    def test_valid_arabic_id(self) -> None:
        from src.api.security import sanitize_id

        assert sanitize_id("nar-أبو") == "nar-أبو"

    def test_empty_id_rejected(self) -> None:
        from src.api.security import sanitize_id

        with pytest.raises(ValueError, match="must not be empty"):
            sanitize_id("")

    def test_injection_attempt_rejected(self) -> None:
        from src.api.security import sanitize_id

        with pytest.raises(ValueError, match="disallowed characters"):
            sanitize_id("nar-001' OR 1=1 //")

    def test_newline_rejected(self) -> None:
        from src.api.security import sanitize_id

        with pytest.raises(ValueError, match="disallowed characters"):
            sanitize_id("nar-001\n}")

    def test_too_long_rejected(self) -> None:
        from src.api.security import sanitize_id

        with pytest.raises(ValueError, match="exceeds maximum length"):
            sanitize_id("a" * 300)


# --- Cypher Audit ---


class TestCypherAudit:
    """Verify the Cypher injection audit scanner."""

    def test_audit_runs_without_error(self) -> None:
        from pathlib import Path

        from src.api.security import audit_cypher_queries

        root = Path(__file__).resolve().parent.parent.parent
        findings = audit_cypher_queries(root)
        # Should return a list (may or may not have findings)
        assert isinstance(findings, list)

    def test_audit_detects_known_fstring(self) -> None:
        """The neo4j_client.py constraint creation uses an f-string — should be flagged."""
        from pathlib import Path

        from src.api.security import audit_cypher_queries

        root = Path(__file__).resolve().parent.parent.parent
        findings = audit_cypher_queries(root)
        constraint_findings = [f for f in findings if "constraint" in f.get("code", "").lower()]
        # The known f-string in neo4j_client.py should be flagged as LOW risk
        assert any("LOW" in f.get("issue", "") for f in constraint_findings)
