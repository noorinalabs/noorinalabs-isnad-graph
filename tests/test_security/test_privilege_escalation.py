"""SEC-03: Privilege escalation tests.

Verifies that non-admin users cannot access admin-only endpoints, and that
role manipulation in JWT claims does not grant elevated access.
Maps to OWASP OTG-AUTHZ-002/003.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ADMIN_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/users/some-user-id"),
    ("GET", "/api/v1/admin/health/live"),
    ("GET", "/api/v1/admin/stats"),
]


class TestNonAdminCannotAccessAdminRoutes:
    """A valid token for a non-admin user must return 403 on admin endpoints."""

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_regular_user_gets_403(
        self, client: TestClient, valid_token: str, method: str, path: str
    ) -> None:
        response = client.request(method, path, headers={"Authorization": f"Bearer {valid_token}"})
        assert response.status_code == 403, (
            f"Non-admin user should get 403 on {method} {path}, got {response.status_code}"
        )

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_admin_user_gets_access(
        self, client: TestClient, admin_token: str, method: str, path: str
    ) -> None:
        """Admin user should pass auth (may get 200 or other non-auth error)."""
        response = client.request(method, path, headers={"Authorization": f"Bearer {admin_token}"})
        # Should NOT be 401 or 403
        assert response.status_code not in (401, 403), (
            f"Admin user should not get {response.status_code} on {method} {path}"
        )


class TestAdminUserUpdate:
    """Non-admin users must not be able to PATCH admin user endpoints."""

    def test_non_admin_cannot_update_user(self, client: TestClient, valid_token: str) -> None:
        response = client.patch(
            "/api/v1/admin/users/some-user-id",
            json={"is_admin": True},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 403

    def test_non_admin_cannot_suspend_user(self, client: TestClient, valid_token: str) -> None:
        response = client.patch(
            "/api/v1/admin/users/other-user",
            json={"is_suspended": True},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 403

    def test_non_admin_cannot_change_role(self, client: TestClient, valid_token: str) -> None:
        response = client.patch(
            "/api/v1/admin/users/other-user",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert response.status_code == 403


class TestRoleManipulationInJWT:
    """Injecting role claims in the JWT must not bypass server-side role checks.

    The server resolves roles from the database (Neo4j), NOT from JWT claims.
    A token with a spoofed role claim should still be rejected if the database
    says the user is not an admin.
    """

    def test_spoofed_admin_role_in_jwt_rejected(self, client: TestClient) -> None:
        """A JWT with 'role: admin' in claims must still be rejected if the
        database user is not an admin."""
        from tests.test_security.conftest import _make_token

        # Create a token with spoofed admin claims -- the user ID maps to a
        # regular user in the mock_neo4j fixture.
        token = _make_token(
            sub="regular-user-001",
            extra_claims={"role": "admin", "is_admin": True},
        )
        response = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, (
            "Spoofed admin role in JWT should not grant admin access"
        )

    def test_unknown_user_cannot_access_admin(self, client: TestClient) -> None:
        """A token for a user not in the database should be treated as non-admin."""
        from tests.test_security.conftest import _make_token

        token = _make_token(sub="unknown-user-999")
        response = client.get(
            "/api/v1/admin/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
