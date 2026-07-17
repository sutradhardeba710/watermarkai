"""Stateless token helpers that have no DB/Redis dependencies.

Kept separate from auth_service so logic tests can import these without
pulling sqlalchemy/greenlet (see tests/test_security.py). auth_service
re-exports these names so callers keep using one entrypoint.
"""
from __future__ import annotations

import time

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import random_token

settings = get_settings()

VERIF_TYPE = "email_verification"


def make_email_verification_token(user_id: str, ttl_hours: int = 24) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "type": VERIF_TYPE, "iat": now, "exp": now + ttl_hours * 3600}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_email_verification_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError as exc:
        raise AppError("INVALID_TOKEN", "Invalid or expired verification link.", 400) from exc
    if payload.get("type") != VERIF_TYPE:
        raise AppError("INVALID_TOKEN", "Invalid verification token.", 400)
    return payload["sub"]


RESET_TYPE = "password_reset"
RESET_TTL_SECONDS = 3600


def make_password_reset_token(user_id: str) -> tuple[str, str]:
    """Return (token, nonce). Caller must store the nonce in Redis (single-use)."""
    now = int(time.time())
    nonce = random_token()
    payload = {"sub": user_id, "type": RESET_TYPE, "iat": now, "exp": now + RESET_TTL_SECONDS, "nonce": nonce}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256"), nonce
