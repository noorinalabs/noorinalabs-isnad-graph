"""SEC-04: Insecure Direct Object Reference (IDOR) tests.

Verifies that users cannot access other users' data by manipulating
entity IDs in request parameters. Maps to OWASP OTG-AUTHZ-004.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestIDORUserEndpoints:
    """Non-admin user must not be able to view or modify other users via admin routes."""

    def test_cannot_view_other_user_via_admin(self, client: TestClient, valid_token: str) -> None:
        """Regular user cannot GET another user's details from admin endpoint."""
        response = client.get(
            "/api/v1/admin/users/admin-user-001",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 403

    def test_cannot_modify_other_user_via_admin(self, client: TestClient, valid_token: str) -> None:
        """Regular user cannot PATCH another user's record."""
        response = client.patch(
            "/api/v1/admin/users/admin-user-001",
            json={"role": "viewer"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 403


class TestIDORMeEndpoint:
    """The /auth/me endpoint must return only the authenticated user's data."""

    def test_me_returns_own_data(self, client: TestClient, valid_token: str) -> None:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "regular-user-001"

    def test_me_does_not_leak_other_users(self, client: TestClient, admin_token: str) -> None:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "admin-user-001"
        # Must not contain other users' data
        assert "regular-user-001" not in response.text


class TestIDEnumeration:
    """Sequential/predictable ID enumeration attempts."""

    @pytest.mark.parametrize(
        "entity_id",
        [
            "1",
            "2",
            "100",
            "0",
            "-1",
            "999999999",
        ],
    )
    def test_sequential_narrator_ids_return_404(
        self, client: TestClient, valid_token: str, entity_id: str
    ) -> None:
        """Attempting sequential numeric IDs should return 404, not leak data."""
        response = client.get(
            f"/api/v1/narrators/{entity_id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        # With the mock returning [], this should be 404
        assert response.status_code in (404, 422)

    @pytest.mark.parametrize(
        "entity_id",
        ["1", "2", "100", "0", "-1"],
    )
    def test_sequential_hadith_ids_return_404(
        self, client: TestClient, valid_token: str, entity_id: str
    ) -> None:
        response = client.get(
            f"/api/v1/hadiths/{entity_id}",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code in (404, 422)
