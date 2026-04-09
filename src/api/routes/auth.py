"""Authentication route stubs for endpoints migrated to user-service.

OAuth login, token issuance, email verification, session management, and
subscription endpoints are now handled by user-service. This module
provides 410 Gone stubs so clients receive a clear migration pointer.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


def _gone(location: str) -> JSONResponse:
    """Return a 410 Gone response pointing to the user-service equivalent."""
    return JSONResponse(
        status_code=410,
        content={
            "detail": "This endpoint has moved to the user service",
            "location": location,
        },
    )


# --- Session management stubs (migrated to user-service) ---


@router.get("/auth/sessions")
def list_sessions() -> JSONResponse:
    return _gone("/api/v1/sessions")


@router.delete("/auth/sessions/{session_id}")
def revoke_session(session_id: str) -> JSONResponse:
    return _gone(f"/api/v1/sessions/{session_id}")


@router.post("/auth/sessions/heartbeat")
def session_heartbeat() -> JSONResponse:
    return _gone("/api/v1/sessions/heartbeat")


# --- Email verification stubs (migrated to user-service) ---


@router.post("/auth/send-verification")
def send_verification() -> JSONResponse:
    return _gone("/api/v1/verification/send")


@router.post("/auth/verify-email")
def verify_email() -> JSONResponse:
    return _gone("/api/v1/verification/confirm")


@router.post("/auth/resend-verification")
def resend_verification() -> JSONResponse:
    return _gone("/api/v1/verification/send")


# --- Subscription stub (migrated to user-service) ---


@router.get("/auth/subscription")
def get_subscription() -> JSONResponse:
    return _gone("/api/v1/subscriptions/me")
