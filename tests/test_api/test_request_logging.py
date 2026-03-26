"""Tests for request logging middleware (request ID, structured log output)."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src.api.middleware import RequestLoggingMiddleware


def _homepage(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def _make_app() -> Starlette:
    """Create a minimal Starlette app with only the RequestLoggingMiddleware."""
    app = Starlette(routes=[Route("/", _homepage)])
    app.add_middleware(RequestLoggingMiddleware)
    return app


class TestRequestLoggingMiddleware:
    """Verify X-Request-ID header and request lifecycle logging."""

    def test_response_includes_request_id(self) -> None:
        """Every response must include an X-Request-ID header."""
        client = TestClient(_make_app())
        resp = client.get("/")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_client_supplied_request_id_is_respected(self) -> None:
        """If the client sends X-Request-ID, the server echoes it back."""
        client = TestClient(_make_app())
        custom_id = "my-trace-id-12345"
        resp = client.get("/", headers={"X-Request-ID": custom_id})
        assert resp.headers["X-Request-ID"] == custom_id

    def test_request_id_truncated_to_64_chars(self) -> None:
        """Overly long request IDs are truncated to 64 characters."""
        client = TestClient(_make_app())
        long_id = "x" * 100
        resp = client.get("/", headers={"X-Request-ID": long_id})
        assert len(resp.headers["X-Request-ID"]) == 64

    def test_auto_generated_request_id_is_hex(self) -> None:
        """Auto-generated request IDs are hex UUID4 strings (32 chars)."""
        client = TestClient(_make_app())
        resp = client.get("/")
        rid = resp.headers["X-Request-ID"]
        # uuid4().hex produces a 32-char lowercase hex string
        assert len(rid) == 32
        assert all(c in "0123456789abcdef" for c in rid)

    def test_unique_ids_per_request(self) -> None:
        """Each request gets a different auto-generated ID."""
        client = TestClient(_make_app())
        ids = {client.get("/").headers["X-Request-ID"] for _ in range(5)}
        assert len(ids) == 5
