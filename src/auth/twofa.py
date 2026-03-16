"""2FA stub endpoints — interfaces designed, not implemented."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/api/v1/auth/2fa/enroll")
async def enroll_2fa() -> None:
    """Enroll a user in 2FA (TOTP or WebAuthn).

    See docs/2fa-design.md for the full design specification.
    """
    raise HTTPException(status_code=501, detail="2FA not yet implemented")


@router.post("/api/v1/auth/2fa/verify")
async def verify_2fa() -> None:
    """Verify a 2FA code during authentication.

    See docs/2fa-design.md for the full design specification.
    """
    raise HTTPException(status_code=501, detail="2FA not yet implemented")


@router.post("/api/v1/auth/2fa/recovery")
async def use_recovery_code() -> None:
    """Use a one-time recovery code to bypass 2FA.

    See docs/2fa-design.md for the full design specification.
    """
    raise HTTPException(status_code=501, detail="2FA not yet implemented")
