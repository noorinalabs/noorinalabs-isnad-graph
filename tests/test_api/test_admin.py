"""Tests for admin API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from contextlib import ExitStack
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import User
from src.api.middleware import require_admin
from src.config import (
    AuthSettings,
    Neo4jSettings,
    PostgresSettings,
    RedisSettings,
    Settings,
    get_settings,
)


def _admin_user() -> User:
    return User(
        id="admin-user",
        email="admin@example.com",
        name="Admin User",
        is_admin=True,
    )


def _regular_user() -> User:
    return User(
        id="regular-user",
        email="user@example.com",
        name="Regular User",
        is_admin=False,
    )


def _test_settings() -> Settings:
    """Build a Settings instance without reading .env."""
    return Settings(
        _env_file=None,
        neo4j=Neo4jSettings(uri="bolt://localhost:7687", user="neo4j", password="test"),
        postgres=PostgresSettings(dsn="postgresql://test:test@localhost:5432/test"),
        redis=RedisSettings(url="redis://localhost:6379/0"),
        auth=AuthSettings(),
    )


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch get_settings to avoid .env parsing errors in tests."""
    test_settings = _test_settings()
    get_settings.cache_clear()

    import src.config

    monkeypatch.setattr(src.config, "get_settings", lambda: test_settings)


@pytest.fixture
def mock_neo4j() -> MagicMock:
    client = MagicMock()
    client.execute_read.return_value = []
    client.execute_write.return_value = []
    return client


@pytest.fixture
def admin_app(mock_neo4j: MagicMock) -> FastAPI:
    """FastAPI app with admin auth override."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    app.dependency_overrides[require_admin] = _admin_user
    return app


@pytest.fixture
def admin_client(admin_app: FastAPI) -> TestClient:
    return TestClient(admin_app)


@pytest.fixture
def noauth_app(mock_neo4j: MagicMock) -> FastAPI:
    """FastAPI app with NO auth overrides — tests 401/403 paths."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    return app


@pytest.fixture
def noauth_client(noauth_app: FastAPI) -> TestClient:
    return TestClient(noauth_app)


@pytest.fixture
def regular_app(mock_neo4j: MagicMock) -> FastAPI:
    """FastAPI app with non-admin user override for require_admin."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j

    from fastapi import HTTPException

    def _raise_not_found() -> User:
        # Mirrors require_admin's hide-existence 404 for non-admins (ig#804).
        raise HTTPException(status_code=404, detail="Not Found")

    app.dependency_overrides[require_admin] = _raise_not_found
    return app


@pytest.fixture
def regular_client(regular_app: FastAPI) -> TestClient:
    return TestClient(regular_app)


# --- Health endpoints ---


class TestAdminHealth:
    def test_liveness(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_readiness(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.return_value = [{"ok": 1}]
        resp = admin_client.get("/api/v1/admin/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ok", "degraded")
        assert "neo4j" in data
        assert "postgres" in data
        assert "redis" in data


class TestAdminHealthObservability:
    """Issue #913 — failing probes must log structured failures without leaking DSN."""

    def test_redact_dsn_strips_basic_auth_userpass(self) -> None:
        from src.api.routes.admin.health import _redact_dsn

        assert _redact_dsn("postgresql://user:secret@host/db") == "postgresql://***@host/db"
        assert _redact_dsn("redis://:topsecret@host:6379/0") == "redis://***@host:6379/0"

    def test_redact_dsn_leaves_dsn_free_text_untouched(self) -> None:
        from src.api.routes.admin.health import _redact_dsn

        assert _redact_dsn("connection refused on port 5432") == "connection refused on port 5432"
        assert _redact_dsn("OperationalError: server closed connection") == (
            "OperationalError: server closed connection"
        )

    def test_neo4j_probe_failure_logs_exc_type_no_dsn(
        self, admin_client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        from structlog.testing import capture_logs

        mock_neo4j.execute_read.side_effect = RuntimeError(
            "auth failed for bolt://neo4j:supersecret@host:7687"
        )
        with capture_logs() as cap_logs, _patched_pg_redis():
            resp = admin_client.get("/api/v1/admin/health/ready")

        assert resp.status_code == 200
        data = resp.json()
        assert data["neo4j"] is False
        assert data["status"] == "degraded"

        neo4j_events = [r for r in cap_logs if "neo4j" in r.get("event", "")]
        assert len(neo4j_events) >= 1, f"expected neo4j failure log, got {cap_logs}"
        ev = neo4j_events[0]
        assert ev["log_level"] == "error"
        assert ev["exc_type"] == "RuntimeError"
        for field_value in ev.values():
            assert "supersecret" not in str(field_value), f"DSN secret leaked in field: {ev}"

    def test_postgres_probe_failure_logs_no_dsn(self, admin_client: TestClient) -> None:
        from unittest.mock import patch

        from structlog.testing import capture_logs

        mock_neo4j = admin_client.app.state.neo4j  # type: ignore[attr-defined]
        mock_neo4j.execute_read.return_value = [{"ok": 1}]

        boom = RuntimeError("connect: postgresql://pguser:pgpass@db:5432/x")
        with capture_logs() as cap_logs:
            with (
                patch("psycopg.connect", side_effect=boom),
                patch("redis.from_url") as mock_redis_from_url,
            ):
                mock_redis_from_url.return_value.ping.return_value = True
                resp = admin_client.get("/api/v1/admin/health/ready")

        assert resp.status_code == 200
        assert resp.json()["postgres"] is False

        pg_events = [r for r in cap_logs if "postgres" in r.get("event", "")]
        assert len(pg_events) == 1
        ev = pg_events[0]
        assert ev["exc_type"] == "RuntimeError"
        assert ev["log_level"] == "error"
        # Mandatory security assertion — DSN password must NOT appear anywhere in the log record
        for field_value in ev.values():
            assert "pgpass" not in str(field_value), f"DSN password leaked: {ev}"
            assert "pguser:pgpass" not in str(field_value)

    def test_redis_probe_failure_logs_no_url_secret(self, admin_client: TestClient) -> None:
        from unittest.mock import patch

        from structlog.testing import capture_logs

        mock_neo4j = admin_client.app.state.neo4j  # type: ignore[attr-defined]
        mock_neo4j.execute_read.return_value = [{"ok": 1}]

        boom = RuntimeError("auth failed: redis://:topsecret@cache:6379/0")
        with capture_logs() as cap_logs:
            with patch("psycopg.connect"), patch("redis.from_url") as mock_redis_from_url:
                mock_redis_from_url.return_value.ping.side_effect = boom
                resp = admin_client.get("/api/v1/admin/health/ready")

        assert resp.status_code == 200
        assert resp.json()["redis"] is False

        redis_events = [r for r in cap_logs if "redis" in r.get("event", "")]
        assert len(redis_events) == 1
        ev = redis_events[0]
        assert ev["exc_type"] == "RuntimeError"
        for field_value in ev.values():
            assert "topsecret" not in str(field_value), f"Redis URL secret leaked: {ev}"

    def test_all_probes_pass_emits_no_failure_logs(
        self, admin_client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        from structlog.testing import capture_logs

        mock_neo4j.execute_read.return_value = [{"ok": 1}]
        with capture_logs() as cap_logs, _patched_pg_redis():
            resp = admin_client.get("/api/v1/admin/health/ready")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        failure_events = [r for r in cap_logs if "health probe failed" in r.get("event", "")]
        assert failure_events == []


def _patched_pg_redis() -> ExitStack:
    """Context manager: stub psycopg.connect and redis.from_url to no-op success."""
    from contextlib import ExitStack
    from unittest.mock import MagicMock, patch

    stack = ExitStack()
    pg_patch = patch("psycopg.connect")
    redis_patch = patch("redis.from_url")
    stack.enter_context(pg_patch)
    mock_redis = stack.enter_context(redis_patch)
    mock_redis.return_value = MagicMock()
    mock_redis.return_value.ping.return_value = True
    return stack


# --- Stats endpoint ---


class TestAdminStats:
    def test_stats_empty(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hadith_count"] == 0
        assert data["narrator_count"] == 0
        assert data["collection_count"] == 0
        assert data["coverage_pct"] == 0.0

    def test_stats_with_data(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.return_value = [
            {
                "hadith_count": 100,
                "narrator_count": 50,
                "collection_count": 6,
                "coverage_pct": 85.5,
            }
        ]
        resp = admin_client.get("/api/v1/admin/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["hadith_count"] == 100
        assert data["narrator_count"] == 50

    def test_stats_empty_has_empty_breakdown(self, admin_client: TestClient) -> None:
        # The corpus-scope fields must always be present (empty when nothing
        # is loaded), so the frontend can render unconditionally.
        resp = admin_client.get("/api/v1/admin/stats")
        data = resp.json()
        assert data["collections"] == []
        assert data["sects"] == []

    def test_stats_corpus_scope_breakdown(
        self, admin_client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        # First execute_read → aggregate row; second → per-collection breakdown.
        mock_neo4j.execute_read.side_effect = [
            [
                {
                    "hadith_count": 14552,
                    "narrator_count": 50,
                    "collection_count": 2,
                    "coverage_pct": 100.0,
                }
            ],
            [
                {"id": "muslim", "name": "Sahih Muslim", "sect": "sunni", "hadith_count": 7314},
                {
                    "id": "bukhari",
                    "name": "Sahih al-Bukhari",
                    "sect": "sunni",
                    "hadith_count": 7238,
                },
            ],
        ]
        resp = admin_client.get("/api/v1/admin/stats")
        assert resp.status_code == 200
        data = resp.json()

        # Per-collection breakdown is surfaced verbatim (incl. sect).
        assert data["collections"] == [
            {"id": "muslim", "name": "Sahih Muslim", "sect": "sunni", "hadith_count": 7314},
            {"id": "bukhari", "name": "Sahih al-Bukhari", "sect": "sunni", "hadith_count": 7238},
        ]
        # Per-sect aggregation rolls the collections up.
        assert data["sects"] == [
            {"sect": "sunni", "hadith_count": 14552, "collection_count": 2},
        ]

    def test_stats_breakdown_defaults_missing_sect_to_unknown(
        self, admin_client: TestClient, mock_neo4j: MagicMock
    ) -> None:
        mock_neo4j.execute_read.side_effect = [
            [
                {
                    "hadith_count": 5,
                    "narrator_count": 0,
                    "collection_count": 1,
                    "coverage_pct": 0.0,
                }
            ],
            [{"id": "mystery", "name": "Mystery", "sect": None, "hadith_count": 5}],
        ]
        resp = admin_client.get("/api/v1/admin/stats")
        data = resp.json()
        assert data["collections"][0]["sect"] == "unknown"
        assert data["sects"] == [
            {"sect": "unknown", "hadith_count": 5, "collection_count": 1},
        ]


# --- Analytics endpoint ---


class TestAdminAnalytics:
    def test_analytics(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert "search_volume" in data
        assert "api_call_count" in data
        assert "popular_narrators" in data


# --- Users endpoints ---


class TestAdminUsers:
    """User management endpoints now return 501 (moved to user-service)."""

    def test_list_users_returns_501(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/users")
        assert resp.status_code == 501

    def test_get_user_returns_501(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/users/u1")
        assert resp.status_code == 501

    def test_update_user_returns_501(self, admin_client: TestClient) -> None:
        resp = admin_client.patch("/api/v1/admin/users/u1", json={"is_admin": True})
        assert resp.status_code == 501

    def test_update_user_role_returns_501(self, admin_client: TestClient) -> None:
        resp = admin_client.patch("/api/v1/admin/users/u1/role", json={"role": "admin"})
        assert resp.status_code == 501


# --- Config endpoints ---


class TestAdminConfig:
    @pytest.fixture(autouse=True)
    def _setup_pg(self, admin_app: FastAPI) -> None:
        """Override the get_pg dependency with a mock PgClient."""
        from src.api.deps import get_pg

        self._pg = MagicMock()
        # Default: no rows in system_config, no rows in config_audit
        self._pg.execute.return_value = []
        admin_app.dependency_overrides[get_pg] = lambda: self._pg

    def test_get_config_defaults(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_limit_per_minute"] == 60
        assert data["cors_origins"] == ["http://localhost:3000"]
        assert data["feature_flags"] == {}
        assert data["max_search_results"] == 100
        assert data["max_pagination_limit"] == 100

    def test_get_config_from_db(self, admin_client: TestClient) -> None:
        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "SELECT key, value FROM system_config" in query:
                return [
                    {"key": "rate_limit_per_minute", "value": "120"},
                    {"key": "cors_origins", "value": '["http://example.com"]'},
                ]
            return []

        self._pg.execute.side_effect = fake_execute
        resp = admin_client.get("/api/v1/admin/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rate_limit_per_minute"] == 120
        assert data["cors_origins"] == ["http://example.com"]
        # Defaults for missing keys
        assert data["max_search_results"] == 100

    def test_update_config(self, admin_client: TestClient) -> None:
        self._pg.execute.return_value = []
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"rate_limit_per_minute": 120},
        )
        assert resp.status_code == 200
        # Verify upsert and audit INSERT calls were made
        calls = self._pg.execute.call_args_list
        upsert_calls = [c for c in calls if "INSERT INTO system_config" in str(c)]
        audit_calls = [c for c in calls if "INSERT INTO config_audit" in str(c)]
        assert len(upsert_calls) >= 1
        assert len(audit_calls) >= 1

    def test_update_config_no_fields(self, admin_client: TestClient) -> None:
        resp = admin_client.patch("/api/v1/admin/config", json={})
        assert resp.status_code == 400

    def test_update_config_rejects_unknown_fields(self, admin_client: TestClient) -> None:
        resp = admin_client.patch(
            "/api/v1/admin/config",
            json={"jwt_secret": "hacked"},
        )
        # Unknown field is ignored by pydantic, so no valid fields → 400
        assert resp.status_code == 400

    def test_audit_log_empty(self, admin_client: TestClient) -> None:
        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "count(*)" in query:
                return [{"total": 0}]
            return []

        self._pg.execute.side_effect = fake_execute
        resp = admin_client.get("/api/v1/admin/config/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entries"] == []
        assert data["total"] == 0

    def test_audit_log_with_entries(self, admin_client: TestClient) -> None:
        def fake_execute(query: str, params: object = None) -> list[dict[str, object]]:
            if "count(*)" in query:
                return [{"total": 1}]
            if "SELECT key, old_value" in query:
                return [
                    {
                        "key": "rate_limit_per_minute",
                        "old_value": "60",
                        "new_value": "120",
                        "changed_by": "admin-user",
                        "changed_at": "2026-03-16 12:00:00+00",
                    }
                ]
            return []

        self._pg.execute.side_effect = fake_execute
        resp = admin_client.get("/api/v1/admin/config/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["entries"]) == 1
        assert data["entries"][0]["key"] == "rate_limit_per_minute"
        assert data["entries"][0]["old_value"] == "60"
        assert data["entries"][0]["new_value"] == "120"


# --- Auth enforcement ---


class TestAdminAuthEnforcement:
    def test_unauthenticated_returns_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.get("/api/v1/admin/stats")
        assert resp.status_code == 401

    def test_non_admin_returns_404(self, regular_client: TestClient) -> None:
        resp = regular_client.get("/api/v1/admin/stats")
        assert resp.status_code == 404
