"""Celery app shared by backend task dispatch and the worker process.

Combined worker for MVP (SRS WORKER-002):
    celery -A workers.celery_app worker -Q detection,processing,encoding -c 2 -l info

Redis-based locking (one worker per job) is implemented in the task modules
via SETNX (SRS WORKER-004).
"""
from __future__ import annotations

import threading
import time

from app.core.config import get_settings
import workers.ai_models_paths  # noqa: F401 — installs ai_models / ai_model_interfaces aliases
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready

from workers.common import heartbeat

settings = get_settings()

celery_app = Celery(
    "vwa",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "workers.tasks.detection",
        "workers.tasks.processing",
        "workers.tasks.maintenance",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Publisher side: the API process imports this app to apply_async but holds
    # the broker connection pool for the process lifetime. On Windows the pooled
    # connection to Redis goes stale (the broker may have been down at import, or
    # the socket died), and apply_async surfaces a kombu OperationalError
    # "connection refused" instead of reconnecting — so /process returns 500 and
    # the job row sits at processing_queued forever (UI: "queued · 0% (0/0
    # frames)"). Disable the pool so each publish opens a fresh connection, and
    # retry on startup so a broker that wasn't ready at import time is tolerated.
    broker_pool_limit=0,
    broker_connection_retry_on_startup=True,
    # Fail fast when the broker is unreachable at publish time. Without a bounded
    # socket timeout, apply_async on a dead Redis blocks for ~2 minutes (kombu's
    # default connect + retry) before raising — the Approve button spins the
    # whole time and finally surfaces a 500. A 5s connect/read timeout plus a
    # bounded publish-retry policy turns that into a prompt, actionable error.
    broker_transport_options={
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
    },
    broker_connection_max_retries=2,
    task_time_limit=settings.job_timeout_seconds,
    task_soft_time_limit=settings.job_timeout_seconds - 60,
    task_default_max_retries=settings.max_retries,
    task_queues={"detection": {}, "processing": {}, "encoding": {}},
    task_routes={
        "workers.tasks.detection.*": {"queue": "detection"},
        "workers.tasks.processing.*": {"queue": "processing"},
        "workers.tasks.encoding.*": {"queue": "encoding"},
        "workers.tasks.maintenance.*": {"queue": "processing"},
    },
    beat_schedule={
        # STORAGE-006 retention sweep every 10 minutes.
        "cleanup-expired-artifacts": {
            "task": "workers.tasks.maintenance.cleanup_expired_artifacts",
            "schedule": 600.0,
        },
        # MON-001..003 metrics + alerts every minute.
        "emit-metrics-snapshot": {
            "task": "workers.tasks.maintenance.emit_metrics_snapshot",
            "schedule": 60.0,
        },
        # BILLING daily credit reset at 00:03 UTC — without this, exhausted
        # users stay at 402 INSUFFICIENT_CREDITS forever.
        "reset-daily-credits": {
            "task": "workers.tasks.maintenance.reset_daily_credits",
            "schedule": crontab(minute=3, hour=0),
        },
    },
)


_heartbeat_thread: threading.Thread | None = None


def _heartbeat_loop(hostname: str) -> None:
    while True:
        heartbeat(hostname)
        time.sleep(30)


def _start_heartbeat(sender=None, **_kwargs) -> None:
    global _heartbeat_thread
    hostname = getattr(sender, "hostname", None)
    if not hostname or (_heartbeat_thread and _heartbeat_thread.is_alive()):
        return
    _heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(str(hostname),),
        name="vwa-worker-heartbeat",
        daemon=True,
    )
    _heartbeat_thread.start()


worker_ready.connect(_start_heartbeat, weak=False)
