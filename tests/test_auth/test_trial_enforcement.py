"""Tests for TrialEnforcementMiddleware."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.auth.tokens import create_access_token


class TestTrialEnforcement:
    """Test that expired trial users are blocked from API but not auth/billing."""

    def test_expired_trial_blocks_api(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        """Expired trial user gets 403 on regular API endpoints."""
        token = create_access_token("test-user", role="viewer")

        # TrialEnforcementMiddleware runs first (LIFO middleware stack)
        # and returns 403 before EmailVerificationMiddleware runs
        expired = datetime.now(UTC) - timedelta(days=1)
        mock_neo4j.execute_read.return_value = [{"status": "expired", "expires": expired}]

        resp = client.get(
            "/api/v1/narrators",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        data = resp.json()
        assert data["code"] == "trial_expired"

    def test_expired_trial_allows_auth(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        """Expired trial user can still access auth endpoints."""
        mock_neo4j.execute_read.return_value = [
            {"status": "expired", "expires": datetime.now(UTC) - timedelta(days=1)}
        ]

        resp = client.get(
            "/api/v1/auth/providers",
        )
        assert resp.status_code == 200

    def test_active_trial_allows_api(self, client: TestClient, mock_neo4j: MagicMock) -> None:
        """Active trial user can access API normally."""
        token = create_access_token("test-user", role="viewer")

        active_expires = datetime.now(UTC) + timedelta(days=5)
        # Call sequence (LIFO middleware stack): (1) trial enforcement check,
        # (2) email verification check, (3) require_auth user lookup,
        # (4) narrators count query, (5) narrators list query
        mock_neo4j.execute_read.side_effect = [
            [{"status": "trial", "expires": active_expires}],  # TrialEnforcementMiddleware
            [{"verified": True}],  # EmailVerificationMiddleware
            [
                {
                    "u": {
                        "id": "test-user",
                        "email": "t@t.com",
                        "name": "T",
                        "provider": "jwt",
                        "provider_user_id": "test-user",
                        "created_at": "2026-01-01T00:00:00",
                        "is_admin": False,
                        "email_verified": True,
                        "subscription_tier": "free",
                        "subscription_status": "trial",
                        "trial_start": None,
                        "trial_expires": None,
                    }
                }
            ],
            [{"total": 0}],
            [],
        ]

        resp = client.get(
            "/api/v1/narrators",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Will get 200 or some other status from the actual narrators route,
        # but NOT 403 from trial enforcement
        assert resp.status_code != 403

    def test_health_exempt(self, client: TestClient) -> None:
        """Health endpoint is never blocked by trial enforcement (no 403)."""
        resp = client.get("/health")
        # Health may return 503 when backing services are mocked/unavailable,
        # but it must never return 403 from trial enforcement.
        assert resp.status_code != 403
