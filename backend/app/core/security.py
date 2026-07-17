"""Password hashing + JWT token utilities (SRS AUTH-006, SEC-001)."""
from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()
_hasher = PasswordHasher()


# --- Passwords (SEC-001) ---


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# --- Password strength (SRS AUTH-001 validation) ---

PASSWORD_RULES_MESSAGE = (
    "Password must be at least 8 characters and include uppercase, lowercase, "
    "a number, and a special character."
)


def is_strong_password(password: str) -> bool:
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(not c.isalnum() for c in password):
        return False
    return True


# --- JWT access / refresh (SRS AUTH-006) ---

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def _create_token(sub: str, token_type: str, ttl_seconds: int, extra: dict[str, Any] | None = None) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "type": token_type,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id,
        TOKEN_TYPE_ACCESS,
        settings.access_token_expire_minutes * 60,
        {"role": role},
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        user_id,
        TOKEN_TYPE_REFRESH,
        settings.refresh_token_expire_days * 86400,
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])


def verify_access_token(token: str) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise JWTError("not an access token")
    return payload


def verify_refresh_token(token: str) -> dict[str, Any]:
    payload = decode_token(token)
    if payload.get("type") != TOKEN_TYPE_REFRESH:
        raise JWTError("not a refresh token")
    return payload


def token_jti(token: str) -> str | None:
    try:
        return decode_token(token).get("jti")
    except JWTError:
        return None


# --- Misc helpers ---


def hash_short(value: str) -> str:
    """Return a non-reversible hash for IP / user-agent fingerprinting (SRS LEGAL-002)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def random_token() -> str:
    return secrets.token_urlsafe(32)


def refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)


def email_verification_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=24)
