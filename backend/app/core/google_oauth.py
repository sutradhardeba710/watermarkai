"""Google Sign-In: verify an ID token issued by Google Identity Services.

The frontend never talks to Google's token endpoint directly with a secret —
the GIS button hands the browser a signed ID token (JWT), which the frontend
forwards to POST /auth/google. We verify it here against Google's public keys,
so the claims below are attacker-proof as long as verification succeeds.
"""
from __future__ import annotations

from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings
from app.core.errors import AppError

settings = get_settings()
_request = google_requests.Request()


@dataclass(frozen=True)
class GoogleProfile:
    sub: str
    email: str
    email_verified: bool
    full_name: str


def verify_google_id_token(credential: str) -> GoogleProfile:
    """Verify an ID token's signature, issuer, audience, and expiry.

    Raises AppError on any verification failure — an invalid/expired/forged
    token must never reach the caller as trusted data.
    """
    if not settings.google_client_id:
        raise AppError("GOOGLE_SIGNIN_DISABLED", "Google sign-in is not configured.", 503)
    try:
        payload = google_id_token.verify_oauth2_token(
            credential, _request, settings.google_client_id
        )
    except ValueError as exc:
        raise AppError("INVALID_TOKEN", "Invalid or expired Google credential.", 401) from exc

    if payload.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise AppError("INVALID_TOKEN", "Invalid Google credential issuer.", 401)

    email = payload.get("email")
    if not email:
        raise AppError("INVALID_TOKEN", "Google account has no email.", 401)

    return GoogleProfile(
        sub=payload["sub"],
        email=email.lower(),
        email_verified=bool(payload.get("email_verified", False)),
        full_name=payload.get("name") or email.split("@")[0],
    )
