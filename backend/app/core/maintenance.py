"""Maintenance-mode gate (PRD §26.6).

The admin panel stores a maintenance blob under ``system_settings.key=
"maintenance"`` (see ``PUT /api/v1/admin/maintenance``). This middleware is
what actually *enforces* it: when enabled, non-exempt API traffic gets a 503
with the configured public message.

The state is read through a small TTL cache so we don't hit Postgres on every
request; the admin PUT endpoint calls :func:`invalidate_cache` so a toggle
takes effect immediately on this process. Reads fail open — a DB hiccup never
takes the site down harder than it already is.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_CACHE_TTL_SECONDS = 5.0
_cache: dict[str, Any] = {"state": None, "read_at": 0.0}


def invalidate_cache() -> None:
    """Called by the admin maintenance PUT so changes apply immediately."""
    _cache["read_at"] = 0.0


def _load_state() -> dict[str, Any]:
    """Current normalised maintenance state, TTL-cached. Fails open."""
    now = time.monotonic()
    if _cache["state"] is not None and (now - _cache["read_at"]) < _CACHE_TTL_SECONDS:
        return _cache["state"]
    from app.core.db import SessionLocal
    from app.repositories import admin as admin_repo
    from app.services import admin_service

    try:
        with SessionLocal() as db:
            raw = admin_repo.get_setting_json(db, admin_service.MAINTENANCE_SETTING_KEY)
        state = admin_service.normalise_maintenance(raw)
    except Exception:  # noqa: BLE001 — fail open
        state = {"maintenance_enabled": False}
    _cache["state"] = state
    _cache["read_at"] = now
    return state


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def maintenance_active(state: dict[str, Any]) -> bool:
    """Enabled AND (if a window is configured) now within the window."""
    if not state.get("maintenance_enabled"):
        return False
    now = datetime.now(timezone.utc)
    start = _parse_dt(state.get("start_time"))
    end = _parse_dt(state.get("end_time"))
    if start and now < start:
        return False
    if end and now > end:
        return False
    return True


def public_state() -> dict[str, Any]:
    """Trimmed maintenance state for the unauthenticated status endpoint."""
    state = _load_state()
    return {
        "maintenance_enabled": maintenance_active(state),
        "public_message": state.get("public_message") or "",
        "end_time": state.get("end_time"),
        "status_page_link": state.get("status_page_link"),
    }


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """Return 503 for non-exempt requests while maintenance is active.

    Exempt: health/status, docs, auth (admins must be able to log in), and the
    admin API when ``allow_administrators`` is on — the admin router's own
    permission dependencies still gate who can actually use it.
    """

    async def dispatch(self, request: Request, call_next):
        state = _load_state()
        if not maintenance_active(state):
            return await call_next(request)

        path = request.url.path
        from app.core.config import get_settings

        prefix = get_settings().api_prefix
        exempt = (
            path == "/"
            or path.startswith("/health")
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path.startswith("/openapi.json")
            or path.startswith(f"{prefix}/auth")
        )
        if state.get("allow_administrators", True) and path.startswith(f"{prefix}/admin"):
            exempt = True
        if request.method == "OPTIONS":  # CORS preflight must succeed
            exempt = True
        if exempt:
            return await call_next(request)

        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {
                    "code": "MAINTENANCE",
                    "message": state.get("public_message")
                    or "We're performing scheduled maintenance. Please check back soon.",
                    "details": {
                        "end_time": state.get("end_time"),
                        "status_page_link": state.get("status_page_link"),
                    },
                },
            },
            headers={"Retry-After": "600"},
        )


__all__ = ["MaintenanceMiddleware", "invalidate_cache", "public_state", "maintenance_active"]
