"""Legal gating (SRS LEGAL-001..004).

Legal wording lives in the frontend (LEGAL-001 ownership checkbox, LEGAL-004
prohibited-use notice). On the backend we record a compliance confirmation row
(LEGAL-002) and gate destructive endpoints behind it (LEGAL-003).
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from app.core.config import get_settings
from app.core.errors import AppError


def gate_unconfirmed(confirmed: bool) -> None:
    """Raise FORBIDDEN unless the project has a live compliance confirmation."""
    if not confirmed:
        raise AppError(
            "LEGAL_CONFIRMATION_REQUIRED",
            "You must confirm ownership before analyzing or processing this project.",
            403,
        )


def hash_ip(ip: str | None, salt: str | None = None) -> str | None:
    if not ip:
        return None
    salt = salt or get_settings().secret_key
    return hashlib.sha256((salt + "|" + ip).encode("utf-8")).hexdigest()[:64]


def summarize_ua(user_agent: str | None) -> str | None:
    """Coarse UA bucket — 'chrome/windows', 'safari/macos', 'other'. Keeps the
    stored value non-identifying while still distinguishing player classes."""
    if not user_agent:
        return None
    ua = user_agent.lower()
    os_part = "windows" if "windows" in ua else "mac" if "macintosh" in ua or "mac os" in ua else "linux" if "linux" in ua else "android" if "android" in ua else "ios" if "iphone" in ua or "ipad" in ua else "other"
    browser_part = "edge" if "edg" in ua else "chrome" if "chrome" in ua else "firefox" if "firefox" in ua else "safari" if "safari" in ua else "other"
    return f"{browser_part}/{os_part}"


__all__ = ["gate_unconfirmed", "hash_ip", "summarize_ua"]
