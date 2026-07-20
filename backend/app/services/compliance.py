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


def gate_processing_allowed(project) -> None:
    """PRD §9.5 / §18: admin moderation flags block processing & analysis.

    A locked project (or one under processing restriction / legal hold) must
    reject analyze, preview, and process requests from its owner.
    """
    if getattr(project, "locked", False):
        raise AppError(
            "PROJECT_LOCKED",
            "This project has been locked by moderation and cannot be processed. Contact support.",
            403,
        )
    if getattr(project, "legal_hold", False):
        raise AppError(
            "LEGAL_HOLD",
            "This project is under a legal hold and cannot be processed. Contact support.",
            403,
        )
    if getattr(project, "processing_restricted", False):
        raise AppError(
            "PROCESSING_RESTRICTED",
            "Processing has been restricted for this project by moderation. Contact support.",
            403,
        )


def gate_downloads_allowed(project) -> None:
    """PRD §9.5 / §18: locked / downloads-disabled projects reject downloads."""
    if getattr(project, "locked", False):
        raise AppError(
            "PROJECT_LOCKED",
            "This project has been locked by moderation; downloads are unavailable. Contact support.",
            403,
        )
    if getattr(project, "downloads_disabled", False):
        raise AppError(
            "DOWNLOADS_DISABLED",
            "Downloads have been disabled for this project by moderation. Contact support.",
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


__all__ = [
    "gate_unconfirmed",
    "gate_processing_allowed",
    "gate_downloads_allowed",
    "hash_ip",
    "summarize_ua",
]
