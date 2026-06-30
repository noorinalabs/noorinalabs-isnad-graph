"""Tests for the admin audit log route + user-service audit client (ig#1140).

The audit trail now lives in user-service's relational ``audit_log`` table, not
on Neo4j ``:AUDIT_LOG`` nodes. These tests exercise the route handler and the
thin httpx client directly, mocking httpx so no live user-service is required.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.api import audit_client
from src.api.deps import get_bearer_token
from src.api.routes.admin.audit import create_audit_entry, list_audit_logs

_TOKEN = "admin-jwt-token"


def _mock_response(json_body: Any, status_code: int = 200) -> MagicMock:
    """Build a MagicMock standing in for an httpx.Response."""
    resp = MagicMock()
    resp.json.return_value = json_body
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestGetBearerToken:
    def test_strips_scheme_prefix(self) -> None:
        request = MagicMock()
        request.headers.get.return_value = "Bearer abc.def.ghi"
        assert get_bearer_token(request) == "abc.def.ghi"

    def test_missing_header_yields_empty(self) -> None:
        request = MagicMock()
        request.headers.get.return_value = ""
        assert get_bearer_token(request) == ""


class TestCreateAuditClient:
    def test_posts_correct_payload_and_forwards_token(self) -> None:
        created = {
            "id": "row-1",
            "action": "data.purge_source",
            "actor_id": "admin-1",
            "actor_name": "Admin One",
            "target_user_id": None,
            "details": "purged",
            "created_at": "2026-06-30T00:00:00Z",
        }
        with patch("src.api.audit_client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response(created)
            result = audit_client.create_audit_log(
                _TOKEN,
                action="data.purge_source",
                actor_id="admin-1",
                actor_name="Admin One",
                details="purged",
            )

        assert result == created
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == f"Bearer {_TOKEN}"
        assert kwargs["json"] == {
            "action": "data.purge_source",
            "actor_id": "admin-1",
            "actor_name": "Admin One",
            "target_user_id": None,
            "details": "purged",
        }
        # Endpoint is the user-service audit path.
        assert mock_post.call_args.args[0].endswith("/api/v1/audit")

    def test_raises_on_non_2xx(self) -> None:
        with patch("src.api.audit_client.httpx.post") as mock_post:
            mock_post.return_value = _mock_response({}, status_code=500)
            with pytest.raises(httpx.HTTPStatusError):
                audit_client.create_audit_log(_TOKEN, action="a", actor_id="admin-1")

    def test_create_audit_entry_delegates_to_client(self) -> None:
        with patch("src.api.routes.admin.audit.audit_client.create_audit_log") as mock_create:
            create_audit_entry(
                _TOKEN,
                action="data.purge_source",
                actor_id="admin-1",
                actor_name="Admin One",
                details="purged",
            )
        mock_create.assert_called_once_with(
            _TOKEN,
            action="data.purge_source",
            actor_id="admin-1",
            actor_name="Admin One",
            target_user_id=None,
            details="purged",
        )


class TestListAuditClient:
    def test_passes_pagination_and_filter_params(self) -> None:
        with patch("src.api.audit_client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(
                {"items": [], "total": 0, "page": 2, "limit": 10}
            )
            audit_client.list_audit_logs(_TOKEN, page=2, limit=10, action="data.purge_source")

        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["Authorization"] == f"Bearer {_TOKEN}"
        assert kwargs["params"] == {"page": 2, "limit": 10, "action": "data.purge_source"}

    def test_omits_action_when_absent(self) -> None:
        with patch("src.api.audit_client.httpx.get") as mock_get:
            mock_get.return_value = _mock_response(
                {"items": [], "total": 0, "page": 1, "limit": 20}
            )
            audit_client.list_audit_logs(_TOKEN, page=1, limit=20)

        _, kwargs = mock_get.call_args
        assert "action" not in kwargs["params"]


class TestListAuditRoute:
    def test_maps_user_service_response(self) -> None:
        payload = {
            "items": [
                {
                    "id": "row-1",
                    "action": "data.purge_source",
                    "actor_id": "admin-1",
                    "actor_name": "Admin One",
                    "target_user_id": None,
                    "details": "purged sunnah",
                    "created_at": "2026-06-30T12:00:00Z",
                },
                {
                    "id": "row-2",
                    "action": "user.suspend",
                    "actor_id": "admin-2",
                    "actor_name": "Admin Two",
                    "target_user_id": "user-9",
                    "details": "abuse",
                    "created_at": "2026-06-29T08:00:00Z",
                },
            ],
            "total": 2,
            "page": 1,
            "limit": 20,
        }
        with patch("src.api.routes.admin.audit.audit_client.list_audit_logs") as mock_list:
            mock_list.return_value = payload
            resp = list_audit_logs(token=_TOKEN, page=1, limit=20, action=None)

        mock_list.assert_called_once_with(_TOKEN, page=1, limit=20, action=None)
        assert resp.total == 2
        assert resp.page == 1
        assert resp.limit == 20
        assert [e.id for e in resp.items] == ["row-1", "row-2"]
        first = resp.items[0]
        assert first.action == "data.purge_source"
        assert first.actor_name == "Admin One"
        assert first.target_user_id is None
        assert resp.items[1].target_user_id == "user-9"
        assert resp.items[0].created_at == "2026-06-30T12:00:00Z"

    def test_forwards_action_filter(self) -> None:
        with patch("src.api.routes.admin.audit.audit_client.list_audit_logs") as mock_list:
            mock_list.return_value = {"items": [], "total": 0, "page": 1, "limit": 50}
            list_audit_logs(token=_TOKEN, page=1, limit=50, action="data.purge_source")

        mock_list.assert_called_once_with(_TOKEN, page=1, limit=50, action="data.purge_source")
