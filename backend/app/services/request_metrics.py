"""Small Redis-backed rolling API metrics shared by all Uvicorn workers."""
from __future__ import annotations

import time
from typing import Any

from app.core.config import get_settings

WINDOW_MINUTES = 5
KEY_PREFIX = "health:api"


def _client():
    import redis

    return redis.from_url(
        get_settings().redis_url,
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )


def record_request(status_code: int, elapsed_ms: float) -> None:
    """Record one response without ever affecting the request outcome."""
    try:
        bucket = int(time.time() // 60)
        key = f"{KEY_PREFIX}:{bucket}"
        pipe = _client().pipeline(transaction=False)
        pipe.hincrby(key, "requests", 1)
        pipe.hincrbyfloat(key, "latency_ms", max(0.0, elapsed_ms))
        if status_code >= 500:
            pipe.hincrby(key, "errors", 1)
        pipe.expire(key, (WINDOW_MINUTES + 2) * 60)
        pipe.execute()
    except Exception:
        # Monitoring must never make the application unavailable.
        return


def snapshot(client: Any | None = None) -> dict[str, float]:
    """Return the five-minute cross-process average latency and 5xx rate."""
    try:
        redis_client = client or _client()
        bucket = int(time.time() // 60)
        keys = [f"{KEY_PREFIX}:{bucket - offset}" for offset in range(WINDOW_MINUTES)]
        pipe = redis_client.pipeline(transaction=False)
        for key in keys:
            pipe.hgetall(key)
        rows = pipe.execute()
        requests = errors = 0
        latency_ms = 0.0
        for row in rows:
            decoded = {
                (key.decode() if isinstance(key, bytes) else str(key)):
                (value.decode() if isinstance(value, bytes) else value)
                for key, value in (row or {}).items()
            }
            requests += int(decoded.get("requests", 0))
            errors += int(decoded.get("errors", 0))
            latency_ms += float(decoded.get("latency_ms", 0.0))
        return {
            "api_response_ms": round(latency_ms / requests, 1) if requests else 0.0,
            "api_error_rate": round((errors / requests) * 100, 2) if requests else 0.0,
        }
    except Exception:
        return {"api_response_ms": 0.0, "api_error_rate": 0.0}


__all__ = ["record_request", "snapshot"]
