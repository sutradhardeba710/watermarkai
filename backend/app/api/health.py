"""Health endpoints (SRS MON-004): /health and sub-checks for DB/Redis/storage/workers."""
from __future__ import annotations

import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.storage import get_storage

router = APIRouter(prefix="/health", tags=["health"])


def _ok(extra: dict | None = None) -> dict:
    return {"status": "ok", **(extra or {})}


@router.get("")
def health() -> dict:
    return _ok({"service": get_settings().app_name, "environment": get_settings().environment})


@router.get("/database")
def health_database() -> dict:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return _ok()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}


@router.get("/redis")
def health_redis() -> dict:
    try:
        import redis

        r = redis.from_url(get_settings().redis_url)
        r.ping()
        return _ok()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}


@router.get("/storage")
def health_storage() -> dict:
    try:
        storage = get_storage()
        # probe with an exists() on a sentinel key
        storage.exists("outputs", "__health_probe__")
        return _ok({"backend": get_settings().storage_backend})
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}


@router.get("/workers")
def health_workers() -> dict:
    """Report workers from the Redis heartbeat hash without a blocking broadcast."""
    try:
        import redis

        client = redis.from_url(get_settings().redis_url)
        raw = client.hgetall("workers:heartbeat") or {}
        now = int(time.time())
        workers = [
            name.decode() if isinstance(name, bytes) else str(name)
            for name, timestamp in raw.items()
            if now - int(timestamp) <= 60
        ]
        if not workers:
            return {"status": "degraded", "workers": []}
        return _ok({"workers": workers})
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}
