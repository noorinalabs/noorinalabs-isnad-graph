"""Security test fixtures.

Provides a FastAPI TestClient that does NOT bypass auth, so we can test
authentication and authorization enforcement end-to-end.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

_TEST_SECRET = "dev-secret-change-in-production"
_TEST_ALGORITHM = "HS256"
_WRONG_SIGNING_KEY = "not-the-real-key-xyzzy"  # gitleaks:allow


def _make_token(
    *,
    sub: str = "test-user-id",
    token_type: str = "access",
    secret: str = _TEST_SECRET,
    algorithm: str = _TEST_ALGORITHM,
    expire_minutes: int = 30,
    extra_claims: dict[str, object] | None = None,
) -> str:
    """Create a JWT token for testing."""
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": sub,
        "type": token_type,
        "exp": now + timedelta(minutes=expire_minutes),
        "iat": now,
        "jti": secrets.token_hex(16),
    }
    if extra_claims:
        payload.update(extra_claims)
    return str(jwt.encode(payload, secret, algorithm=algorithm))


def _make_expired_token(*, sub: str = "test-user-id") -> str:
    """Create a JWT token that expired 1 hour ago."""
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": sub,
        "type": "access",
        "exp": now - timedelta(hours=1),
        "iat": now - timedelta(hours=2),
        "jti": secrets.token_hex(16),
    }
    return str(jwt.encode(payload, _TEST_SECRET, algorithm=_TEST_ALGORITHM))


@pytest.fixture
def valid_token() -> str:
    """A valid access token for a regular (non-admin) user."""
    return _make_token(sub="regular-user-001")


@pytest.fixture
def admin_token() -> str:
    """A valid access token for an admin user (looked up in Neo4j mock)."""
    return _make_token(sub="admin-user-001")


@pytest.fixture
def expired_token() -> str:
    """An expired JWT access token."""
    return _make_expired_token()


@pytest.fixture
def refresh_token_as_access() -> str:
    """A refresh token (wrong type for protected endpoints)."""
    return _make_token(sub="test-user-id", token_type="refresh")


@pytest.fixture
def forged_token() -> str:
    """A token signed with the wrong secret."""
    return _make_token(sub="test-user-id", secret=_WRONG_SIGNING_KEY)


@pytest.fixture
def mock_neo4j() -> MagicMock:
    """Mock Neo4jClient that returns no results by default.

    For admin user lookups, returns is_admin=True when user_id matches
    'admin-user-001'. Otherwise returns a regular user.
    """
    client = MagicMock()

    def _execute_read(query: str, params: dict | None = None) -> list:
        if params and params.get("user_id") == "admin-user-001":
            return [
                {
                    "u": {
                        "id": "admin-user-001",
                        "email": "admin@example.com",
                        "name": "Admin User",
                        "provider": "github",
                        "is_admin": True,
                        "role": "admin",
                    }
                }
            ]
        if params and params.get("user_id") == "regular-user-001":
            return [
                {
                    "u": {
                        "id": "regular-user-001",
                        "email": "user@example.com",
                        "name": "Regular User",
                        "provider": "github",
                        "is_admin": False,
                        "role": "viewer",
                    }
                }
            ]
        return []

    client.execute_read.side_effect = _execute_read
    client.execute_write.return_value = []
    return client


@pytest.fixture
def app(mock_neo4j: MagicMock) -> FastAPI:
    """FastAPI app with mocked Neo4j but real auth middleware (no bypass)."""
    from src.api.app import create_app

    application = create_app()
    application.state.neo4j = mock_neo4j
    # NOTE: We intentionally do NOT override require_auth / require_admin
    # so that real JWT validation logic is exercised.
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Test client with real auth enforcement."""
    return TestClient(app, raise_server_exceptions=False)
