"""API test fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware import require_auth
from src.auth.models import User


def _fake_user() -> User:
    return User(
        id="test-user",
        email="test@example.com",
        name="Test User",
        provider="jwt",
        provider_user_id="test-user",
        created_at=datetime.now(UTC),
    )


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
