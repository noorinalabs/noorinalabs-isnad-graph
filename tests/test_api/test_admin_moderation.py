"""Tests for admin moderation endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware import require_admin
from src.auth.models import User
from tests.test_api.test_admin import (
    _admin_user,
    _test_settings,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    test_settings = _test_settings()
    from src.config import get_settings

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
    from src.api.app import create_app

    app = create_app()
    app.state.neo4j = mock_neo4j
    app.dependency_overrides[require_admin] = _admin_user
    return app


@pytest.fixture
def admin_client(admin_app: FastAPI) -> TestClient:
    return TestClient(admin_app)


@pytest.fixture
def mock_moderation_data() -> list[dict[str, object]]:
    return [
        {
            "props": {
                "id": "mod:hadith:h1:2026-03-16T00:00:00",
                "entity_type": "hadith",
                "entity_id": "h1",
                "reason": "Incorrect attribution",
                "status": "pending",
                "flagged_at": "2026-03-16T00:00:00",
            }
        },
        {
            "props": {
                "id": "mod:narrator:n1:2026-03-16T00:00:00",
                "entity_type": "narrator",
                "entity_id": "n1",
                "reason": "Duplicate entry",
                "status": "pending",
                "flagged_at": "2026-03-16T01:00:00",
            }
        },
    ]


class TestListFlaggedContent:
    def test_list_empty(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.side_effect = [[{"total": 0}], []]
        resp = admin_client.get("/api/v1/admin/moderation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_with_items(
        self,
        admin_client: TestClient,
        mock_neo4j: MagicMock,
        mock_moderation_data: list[dict[str, object]],
    ) -> None:
        mock_neo4j.execute_read.side_effect = [
            [{"total": 2}],
            mock_moderation_data,
        ]
        resp = admin_client.get("/api/v1/admin/moderation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["entity_type"] == "hadith"
        assert data["items"][1]["entity_type"] == "narrator"

    def test_list_pagination(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.side_effect = [[{"total": 50}], []]
        resp = admin_client.get("/api/v1/admin/moderation?page=3&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 50
        assert data["page"] == 3
        assert data["limit"] == 10

    def test_list_filter_by_status(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_read.side_effect = [[{"total": 1}], []]
        resp = admin_client.get("/api/v1/admin/moderation?status=approved")
        assert resp.status_code == 200


class TestUpdateModerationItem:
    def test_approve(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_write.return_value = [
            {
                "props": {
                    "id": "mod:hadith:h1:2026-03-16",
                    "entity_type": "hadith",
                    "entity_id": "h1",
                    "reason": "test",
                    "status": "approved",
                    "flagged_at": "2026-03-16T00:00:00",
                    "resolved_at": "2026-03-16T01:00:00",
                    "notes": "Looks good",
                }
            }
        ]
        resp = admin_client.patch(
            "/api/v1/admin/moderation/mod:hadith:h1:2026-03-16",
            json={"status": "approved", "notes": "Looks good"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_reject(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_write.return_value = [
            {
                "props": {
                    "id": "mod:hadith:h1:2026-03-16",
                    "entity_type": "hadith",
                    "entity_id": "h1",
                    "reason": "test",
                    "status": "rejected",
                    "flagged_at": "2026-03-16T00:00:00",
                    "resolved_at": "2026-03-16T01:00:00",
                    "notes": None,
                }
            }
        ]
        resp = admin_client.patch(
            "/api/v1/admin/moderation/mod:hadith:h1:2026-03-16",
            json={"status": "rejected"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_invalid_status(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        resp = admin_client.patch(
            "/api/v1/admin/moderation/some-id",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422

    def test_not_found(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_write.return_value = []
        resp = admin_client.patch(
            "/api/v1/admin/moderation/nonexistent",
            json={"status": "approved"},
        )
        assert resp.status_code == 404


class TestFlagContent:
    def test_flag_hadith(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_write.return_value = [
            {
                "props": {
                    "id": "mod:hadith:h1:2026-03-16T00:00:00",
                    "entity_type": "hadith",
                    "entity_id": "h1",
                    "reason": "Suspect chain",
                    "status": "pending",
                    "flagged_at": "2026-03-16T00:00:00",
                }
            }
        ]
        resp = admin_client.post(
            "/api/v1/admin/moderation/flag",
            json={"entity_type": "hadith", "entity_id": "h1", "reason": "Suspect chain"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["entity_type"] == "hadith"
        assert data["status"] == "pending"

    def test_flag_narrator(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        mock_neo4j.execute_write.return_value = [
            {
                "props": {
                    "id": "mod:narrator:n1:2026-03-16T00:00:00",
                    "entity_type": "narrator",
                    "entity_id": "n1",
                    "reason": "Duplicate",
                    "status": "pending",
                    "flagged_at": "2026-03-16T00:00:00",
                }
            }
        ]
        resp = admin_client.post(
            "/api/v1/admin/moderation/flag",
            json={"entity_type": "narrator", "entity_id": "n1", "reason": "Duplicate"},
        )
        assert resp.status_code == 201
        assert resp.json()["entity_type"] == "narrator"

    def test_invalid_entity_type(self, admin_client: TestClient, mock_neo4j: MagicMock) -> None:
        resp = admin_client.post(
            "/api/v1/admin/moderation/flag",
            json={"entity_type": "collection", "entity_id": "c1", "reason": "test"},
        )
        assert resp.status_code == 400


class TestModerationAuthEnforcement:
    @pytest.fixture
    def noauth_app(self, mock_neo4j: MagicMock) -> FastAPI:
        from src.api.app import create_app

        app = create_app()
        app.state.neo4j = mock_neo4j
        return app

    @pytest.fixture
    def noauth_client(self, noauth_app: FastAPI) -> TestClient:
        return TestClient(noauth_app)

    @pytest.fixture
    def regular_app(self, mock_neo4j: MagicMock) -> FastAPI:
        from fastapi import HTTPException

        from src.api.app import create_app

        app = create_app()
        app.state.neo4j = mock_neo4j

        def _raise_forbidden() -> User:
            raise HTTPException(status_code=403, detail="Admin access required")

        app.dependency_overrides[require_admin] = _raise_forbidden
        return app

    @pytest.fixture
    def regular_client(self, regular_app: FastAPI) -> TestClient:
        return TestClient(regular_app)

    def test_list_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.get("/api/v1/admin/moderation")
        assert resp.status_code == 401

    def test_list_403(self, regular_client: TestClient) -> None:
        resp = regular_client.get("/api/v1/admin/moderation")
        assert resp.status_code == 403

    def test_patch_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.patch("/api/v1/admin/moderation/some-id", json={"status": "approved"})
        assert resp.status_code == 401

    def test_patch_403(self, regular_client: TestClient) -> None:
        resp = regular_client.patch("/api/v1/admin/moderation/some-id", json={"status": "approved"})
        assert resp.status_code == 403

    def test_flag_401(self, noauth_client: TestClient) -> None:
        resp = noauth_client.post(
            "/api/v1/admin/moderation/flag",
            json={"entity_type": "hadith", "entity_id": "h1", "reason": "test"},
        )
        assert resp.status_code == 401

    def test_flag_403(self, regular_client: TestClient) -> None:
        resp = regular_client.post(
            "/api/v1/admin/moderation/flag",
            json={"entity_type": "hadith", "entity_id": "h1", "reason": "test"},
        )
        assert resp.status_code == 403
