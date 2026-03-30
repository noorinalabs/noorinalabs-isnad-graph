"""SEC-06: Security headers and middleware validation.

Verifies that OWASP-recommended security headers are present on all responses,
and that request size limits are enforced.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestSecurityHeaders:
    """Verify OWASP security headers on responses."""

    def test_x_content_type_options(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers.get("X-Frame-Options") in ("DENY", "SAMEORIGIN")

    def test_x_xss_protection(self, client: TestClient) -> None:
        response = client.get("/health")
        xss_prot = response.headers.get("X-XSS-Protection")
        # Modern recommendation is "0" (disable XSS auditor to avoid
        # false-positive XSS attacks). "1; mode=block" is also acceptable.
        assert xss_prot in ("0", "1; mode=block"), (
            f"X-XSS-Protection should be '0' or '1; mode=block', got {xss_prot!r}"
        )

    def test_strict_transport_security(self, client: TestClient) -> None:
        response = client.get("/health")
        hsts = response.headers.get("Strict-Transport-Security", "")
        assert "max-age=" in hsts

    def test_content_security_policy(self, client: TestClient) -> None:
        response = client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")
        assert len(csp) > 0, "Content-Security-Policy header must be present"

    def test_referrer_policy(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers.get("Referrer-Policy") is not None

    def test_permissions_policy(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers.get("Permissions-Policy") is not None

    def test_request_id_header_generated(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers.get("X-Request-ID") is not None

    def test_request_id_header_respected(self, client: TestClient) -> None:
        custom_id = "custom-request-id-12345"
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.headers.get("X-Request-ID") == custom_id

    def test_request_id_truncated_to_64_chars(self, client: TestClient) -> None:
        long_id = "a" * 100
        response = client.get("/health", headers={"X-Request-ID": long_id})
        assert len(response.headers.get("X-Request-ID", "")) <= 64


class TestRequestSizeLimit:
    """Verify request body size enforcement."""

    def test_small_body_accepted(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/login/google",
            content="{}",
            headers={"Content-Type": "application/json"},
        )
        # Should not be 413 (may be 400 for other reasons)
        assert response.status_code != 413

    def test_body_at_limit_accepted(self, client: TestClient) -> None:
        body = "x" * 1_048_576
        response = client.post(
            "/api/v1/auth/login/google",
            content=body,
            headers={
                "Content-Length": str(len(body)),
                "Content-Type": "application/json",
            },
        )
        # At exactly the limit, should not be 413
        assert response.status_code != 413

    def test_body_over_limit_rejected(self, client: TestClient) -> None:
        body = "x" * (1_048_576 + 1)
        response = client.post(
            "/api/v1/auth/login/google",
            content=body,
            headers={
                "Content-Length": str(len(body)),
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 413

    def test_invalid_content_length_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/login/google",
            content="{}",
            headers={
                "Content-Length": "not-a-number",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 400


class TestCORSPolicy:
    """Verify CORS is configured and does not allow wildcard origins."""

    def test_cors_does_not_allow_wildcard(self, client: TestClient) -> None:
        response = client.options(
            "/api/v1/narrators",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_origin = response.headers.get("Access-Control-Allow-Origin", "")
        assert allow_origin != "*", "CORS must not allow wildcard origins"
