"""Auth test fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.auth.pg_users as _pg_users_mod
import src.utils.pg_client as _pg_client_mod
from src.auth.models import User
from src.config import (
    AuthSettings,
    Neo4jSettings,
    PostgresSettings,
    RedisSettings,
    Settings,
    get_settings,
)


def _make_pg_user(_pg: object, user_id: str) -> User:
    """Build a User as it would come from PostgreSQL (matches get_user_by_id signature)."""
    return User(
        id=user_id,
        email=f"{user_id}@test.com",
        name=user_id,
        provider="google",
        provider_user_id=user_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture(autouse=True)
def _clean_settings_cache() -> None:
    """Clear get_settings cache before each test."""
    get_settings.cache_clear()


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Test settings with safe defaults."""
    monkeypatch.delenv("PG_DSN", raising=False)
    for key in list(os.environ):
        if key.startswith(("NEO4J_", "PG_", "REDIS_", "AUTH_")):
            monkeypatch.delenv(key, raising=False)
    return Settings(
        _env_file=None,
        neo4j=Neo4jSettings(
            _env_file=None, uri="bolt://localhost:7687", user="neo4j", password="test"
        ),
        postgres=PostgresSettings(_env_file=None, dsn="postgresql://test:test@localhost:5432/test"),
        redis=RedisSettings(_env_file=None, url="redis://localhost:6379/0"),
        auth=AuthSettings(_env_file=None, jwt_secret="test-secret", jwt_algorithm="HS256"),
    )


@pytest.fixture(autouse=True)
def _patch_settings(test_settings: Settings) -> Iterator[None]:
    """Patch get_settings at every import site so all auth code uses test settings."""
    targets = [
        "src.config.get_settings",
        "src.auth.tokens.get_settings",
        "src.auth.providers.get_settings",
        "src.api.routes.auth.get_settings",
    ]
    patches = [patch(t, return_value=test_settings) for t in targets]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture(autouse=True)
def _mock_pg_lookup() -> Iterator[None]:
    """Mock PgClient and get_user_by_id so require_auth works without real PG."""
    mock_client = MagicMock()
    mock_client.close = MagicMock()

    with (
        patch.object(_pg_client_mod, "PgClient", return_value=mock_client),
        patch.object(_pg_users_mod, "get_user_by_id", side_effect=_make_pg_user),
    ):
        yield


@pytest.fixture
def mock_neo4j() -> MagicMock:
    """Mock Neo4jClient."""
    client = MagicMock()
    client.execute_read.return_value = []
    client.execute_write.return_value = []
    return client


@pytest.fixture
def app(mock_neo4j: MagicMock) -> FastAPI:
    """FastAPI test application."""
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """TestClient for auth tests."""
    return TestClient(app)
