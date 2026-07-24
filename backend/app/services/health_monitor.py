"""Bounded live dependency probes for the admin system-health board."""
from __future__ import annotations

import smtplib
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any, Callable

import httpx
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import WebhookEvent
from app.services import request_metrics
from app.storage import get_storage
from app.storage.local_fs import mint_signed_token, parse_signed_token

settings = get_settings()

_CACHE_TTL_SECONDS = 300
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def _result(ok: bool | None, detail: str, started: float) -> dict[str, Any]:
    return {
        "ok": ok,
        "detail": detail,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def _run_probe(probe: Callable[[], tuple[bool | None, str]]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        ok, detail = probe()
        return _result(ok, detail, started)
    except Exception:
        return _result(False, "Probe failed", started)


def _cached_probe(name: str, probe: Callable[[], tuple[bool | None, str]]) -> dict[str, Any]:
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(name)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]
    result = _run_probe(probe)
    with _cache_lock:
        _cache[name] = (now, result)
    return result


def _http_probe(url: str, expected: str) -> tuple[bool, str]:
    response = httpx.get(url, timeout=3.0, follow_redirects=True)
    return response.status_code < 500, f"{expected} returned HTTP {response.status_code}"


def _frontend_probe() -> tuple[bool, str]:
    url = "http://frontend:3000" if settings.environment == "prod" else settings.app_base_url
    return _http_probe(url, "Frontend")


def _backend_probe() -> tuple[bool, str]:
    return _http_probe("http://127.0.0.1:8000/health", "Backend")


def _storage_probe() -> tuple[bool, str]:
    storage = get_storage()
    bucket = "outputs"
    key = "__health_probe__"
    try:
        storage.put(bucket, key, BytesIO(b"ok"), content_type="text/plain")
        healthy = storage.get(bucket, key) == b"ok"
        return healthy, f"{settings.storage_backend} read/write probe"
    finally:
        try:
            storage.delete(bucket, key)
        except Exception:
            pass


def _razorpay_probe() -> tuple[bool, str]:
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        return False, "Live API credentials are not configured"
    response = httpx.get(
        "https://api.razorpay.com/v1/plans",
        params={"count": 1},
        auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
        timeout=4.0,
    )
    return response.status_code == 200, f"Razorpay API returned HTTP {response.status_code}"


def _email_probe() -> tuple[bool, str]:
    if settings.smtp_console or not settings.smtp_host:
        return False, "SMTP delivery is not configured"
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=4) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
    return True, "SMTP connection and authentication succeeded"


def _signed_url_probe() -> tuple[bool, str]:
    token = mint_signed_token("outputs", "__health_probe__", 60)
    bucket, key = parse_signed_token(f"token:{token}")
    return (bucket, key) == ("outputs", "__health_probe__"), "Signed token round-trip succeeded"


def _redis_snapshot() -> tuple[dict[str, Any], Any | None, dict[str, int]]:
    started = time.perf_counter()
    try:
        import redis

        client = redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        info = client.info("memory")
        raw = client.hgetall("workers:heartbeat") or {}
        now = int(time.time())
        heartbeats = {
            (name.decode() if isinstance(name, bytes) else str(name)): int(timestamp)
            for name, timestamp in raw.items()
            if now - int(timestamp) <= 60
        }
        probe = _result(True, "PING succeeded", started)
        probe["memory_mb"] = round(float(info.get("used_memory", 0)) / 1024 / 1024, 1)
        return probe, client, heartbeats
    except Exception:
        return _result(False, "Redis probe failed", started), None, {}


def _database_snapshot(db: Session) -> tuple[dict[str, Any], dict[str, float]]:
    started = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        try:
            active, maximum = db.execute(text(
                "SELECT count(*), current_setting('max_connections')::int "
                "FROM pg_stat_activity WHERE datname = current_database()"
            )).one()
            usage = round((float(active) / max(float(maximum), 1.0)) * 100, 1)
        except Exception:
            usage = 0.0
        return _result(True, "SELECT 1 succeeded", started), {
            "db_latency_ms": latency_ms,
            "db_connections": usage,
        }
    except Exception:
        return _result(False, "Database probe failed", started), {
            "db_latency_ms": 0.0,
            "db_connections": 0.0,
        }


def _webhook_failures(db: Session) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    return int(db.execute(
        select(func.count(WebhookEvent.id)).where(
            WebhookEvent.created_at >= since,
            or_(WebhookEvent.status == "failed", WebhookEvent.signature_valid.is_(False)),
        )
    ).scalar() or 0)


def collect(db: Session, base_metrics: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Collect all service checks and metric values for one admin response."""
    database, db_metrics = _database_snapshot(db)
    redis_probe, redis_client, heartbeats = _redis_snapshot()

    probes: dict[str, dict[str, Any]] = {
        "postgres": database,
        "redis": redis_probe,
        "celery": {
            "ok": bool(heartbeats),
            "detail": f"{len(heartbeats)} fresh worker heartbeat(s)",
            "latency_ms": 0.0,
        },
        "gpu_workers": {
            "ok": bool(heartbeats),
            "detail": f"{len(heartbeats)} processing worker(s) online",
            "latency_ms": 0.0,
        },
        "signed_url": _run_probe(_signed_url_probe),
    }

    tasks = {
        "frontend": lambda: _cached_probe("frontend", _frontend_probe),
        "backend": lambda: _cached_probe("backend", _backend_probe),
        "object_storage": lambda: _cached_probe("object_storage", _storage_probe),
        "razorpay": lambda: _cached_probe("razorpay", _razorpay_probe),
        "email": lambda: _cached_probe("email", _email_probe),
    }
    with ThreadPoolExecutor(max_workers=len(tasks), thread_name_prefix="health-probe") as pool:
        futures = {name: pool.submit(task) for name, task in tasks.items()}
        for name, future in futures.items():
            probes[name] = future.result()

    metrics = dict(base_metrics)
    metrics.update(db_metrics)
    metrics.update(request_metrics.snapshot(redis_client))
    metrics.update({
        "redis_memory_mb": redis_probe.get("memory_mb", 0.0),
        "storage_io_failures": 0 if probes["object_storage"]["ok"] else 1,
        "webhook_failures": _webhook_failures(db),
        "email_failures": 0 if probes["email"]["ok"] else 1,
    })
    return probes, metrics


__all__ = ["collect"]
