"""API test fixtures.

Shared fixtures for all ``tests/test_api`` modules. Admin test files
(``test_admin*.py``) previously each defined their own copies of the
settings-cache shim, ``mock_neo4j``, and the admin/noauth/regular app+client
fixtures; those now live here so the admin suite shares a single source.

Note: ``_test_settings()`` builds ``AuthSettings()`` with its class defaults and
deliberately does *not* set ``user_service_url`` / ``user_service_jwks_cache_ttl``.
That distinction is intentional — ``tests/test_auth/conftest.py`` keeps a
separate settings fixture that *does* populate the auth fields, and the two
must not be merged.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api.auth import User
from src.api.middleware import require_admin, require_auth
from src.config import (
    AuthSettings,
    Neo4jSettings,
    PostgresSettings,
    RedisSettings,
    Settings,
    get_settings,
)


def _fake_user() -> User:
    return User(
        id="test-user",
        email="test@example.com",
        name="Test User",
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
    """Build a Settings instance without reading .env.

    Uses ``AuthSettings()`` defaults — see the module docstring for why the
    auth fields are intentionally left unset.
    """
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
    """Mock Neo4jClient for API tests."""
    client = MagicMock()
    client.execute_read.return_value = []
    client.execute_write.return_value = []
    return client


@pytest.fixture
def app(mock_neo4j: MagicMock) -> FastAPI:
    """FastAPI app with mocked Neo4j and auth bypassed."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    app.dependency_overrides[require_auth] = _fake_user
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Test client."""
    return TestClient(app)


# --- Admin app/client fixtures (shared across test_admin*.py) ---


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
    """FastAPI app with NO auth overrides — tests 401 paths."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    return app


@pytest.fixture
def noauth_client(noauth_app: FastAPI) -> TestClient:
    return TestClient(noauth_app)


@pytest.fixture
def regular_app(mock_neo4j: MagicMock) -> FastAPI:
    """FastAPI app with non-admin user override for require_admin — tests 403 paths."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j

    def _raise_forbidden() -> User:
        raise HTTPException(status_code=403, detail="Admin access required")

    app.dependency_overrides[require_admin] = _raise_forbidden
    return app


@pytest.fixture
def regular_client(regular_app: FastAPI) -> TestClient:
    return TestClient(regular_app)
