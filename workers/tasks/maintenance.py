"""Maintenance Celery tasks (SRS STORAGE-006, MON-001..003).

Two periodic tasks, both on the ``processing`` queue so the combined worker
picks them up alongside encode jobs:

* ``cleanup_expired_artifacts`` — walks video_projects, computes a cleanup
  plan via :mod:`app.services.retention`, deletes expired storage keys, and
  soft-deletes expired output rows. Runs every 10 minutes.
* ``emit_metrics_snapshot`` — assembles a :class:`MetricsSnapshot`, evaluates
  alert rules, and publishes a Redis pub/sub event the admin dashboard can
  subscribe to. Runs every minute.

Both are idempotent and safe to run concurrently with the main pipeline; the
cleanup only touches artifacts whose window has elapsed, never in-flight ones.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import JobState, OutputFile, ProcessingJob, VideoProject
from app.services import admin_service, retention

settings = get_settings()


def _run_cleanup() -> dict:
    """Execute one cleanup sweep. Returns a summary dict for logging/audit."""
    from app.storage import get_storage

    storage = get_storage()
    policy = retention.RetentionPolicy(
        retain_original_hours=settings.retain_original_hours,
        retain_preview_hours=settings.retain_preview_hours,
        retain_output_days=settings.retain_output_days,
        retain_failed_hours=settings.retain_failed_hours,
    )
    db = SessionLocal()
    deleted = 0
    errors = 0
    # Which project column each bucket's key lives in — cleared after delete so
    # the next sweep doesn't re-plan the same artifact and download endpoints
    # stop signing URLs for objects that no longer exist.
    key_attr_for_bucket = {
        "originals": "input_storage_key",
        "proxies": "proxy_storage_key",
        "previews": "preview_storage_key",
        "outputs": "output_storage_key",
    }
    try:
        rows = db.execute(select(VideoProject)).scalars()
        for p in rows:
            for action in retention.plan_project_cleanup(p, policy):
                try:
                    storage.delete(action.bucket, action.key)
                    attr = key_attr_for_bucket.get(action.bucket)
                    if attr is not None and getattr(p, attr, None) == action.key:
                        setattr(p, attr, None)
                    deleted += 1
                except Exception:  # noqa: BLE001 — best-effort, keep sweeping
                    errors += 1
            # Expire output-file rows past their window (STORAGE-006 output 7d).
            if p.completed_at is not None:
                out_cut = datetime.now(timezone.utc) - timedelta(days=policy.retain_output_days)
                if p.completed_at < out_cut and p.output_storage_key:
                    db.query(OutputFile).filter(
                        OutputFile.project_id == p.id
                    ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    return {"deleted": deleted, "errors": errors}


@shared_task(name="workers.tasks.maintenance.cleanup_expired_artifacts", queue="processing")
def cleanup_expired_artifacts() -> dict:
    """STORAGE-006 retention sweep. Scheduled via celery beat (see
    ``workers/celery_app.py`` ``beat_schedule``)."""
    try:
        return _run_cleanup()
    except Exception:  # noqa: BLE001 — never let a periodic task crash the beat
        return {"deleted": 0, "errors": -1}


def _snapshot() -> retention.MetricsSnapshot:
    """Assemble the current MON metrics from the DB + Redis heartbeats."""
    from app.repositories import admin as admin_repo

    db = SessionLocal()
    try:
        queue = admin_repo.queue_length(db)
        nodes = admin_repo.list_worker_nodes(db)
        total = len(nodes)
        heartbeats = _heartbeats()
        active = sum(
            1 for w in admin_service.fuse_workers(nodes, heartbeats) if w.online
        )
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        failed_last_hour = _count_failed_since(db, since)
        storage_bytes = admin_repo.storage_bytes(db)
        snap = retention.MetricsSnapshot(
            queue_length=queue,
            active_workers=active,
            total_workers=total,
            failed_jobs_last_hour=failed_last_hour,
            storage_bytes=storage_bytes,
            alerts=[],
        )
        snap = retention.MetricsSnapshot(
            queue_length=snap.queue_length,
            active_workers=snap.active_workers,
            total_workers=snap.total_workers,
            failed_jobs_last_hour=snap.failed_jobs_last_hour,
            storage_bytes=snap.storage_bytes,
            alerts=retention.alerts_for(snap),
        )
        return snap
    finally:
        db.close()


def _count_failed_since(db, since) -> int:
    from sqlalchemy import func

    return int(
        db.execute(
            select(func.count()).select_from(ProcessingJob).where(
                ProcessingJob.status == JobState.failed, ProcessingJob.completed_at >= since
            )
        ).scalar() or 0
    )


def _heartbeats() -> dict[str, int]:
    try:
        import redis as _redis_mod

        r = _redis_mod.from_url(settings.redis_url)
        raw = r.hgetall("workers:heartbeat") or {}
        return {k.decode(): int(v) for k, v in raw.items()} if raw else {}
    except Exception:  # noqa: BLE001
        return {}


@shared_task(name="workers.tasks.maintenance.emit_metrics_snapshot", queue="processing")
def emit_metrics_snapshot() -> dict:
    """MON-001..003: publish a metrics snapshot + raised alerts to Redis
    pub/sub channel ``metrics:snapshot`` so the admin UI can tail it."""
    try:
        import redis as _redis_mod

        snap = _snapshot()
        payload = {
            "queue_length": snap.queue_length,
            "active_workers": snap.active_workers,
            "total_workers": snap.total_workers,
            "failed_jobs_last_hour": snap.failed_jobs_last_hour,
            "storage_bytes": snap.storage_bytes,
            "alerts": snap.alerts,
            "ts": int(time.time()),
        }
        r = _redis_mod.from_url(settings.redis_url)
        r.publish("metrics:snapshot", json.dumps(payload))
        return payload
    except Exception:  # noqa: BLE001
        return {"alerts": [], "ts": int(time.time()), "error": "snapshot_failed"}


@shared_task(name="workers.tasks.maintenance.reset_daily_credits", queue="processing")
def reset_daily_credits_task() -> dict:
    """BILLING: daily credit reset (PRD §17). Scheduled via celery beat —
    without this, users who exhaust their allowance stay at 402
    INSUFFICIENT_CREDITS forever (the 402 message promises a daily reset)."""
    from app.services.payment_service import reset_daily_credits

    db = SessionLocal()
    try:
        count = reset_daily_credits(db)
        db.commit()
        return {"users_reset": count}
    except Exception:  # noqa: BLE001 — never let a periodic task crash the beat
        db.rollback()
        return {"users_reset": 0, "error": "reset_failed"}
    finally:
        db.close()


__all__ = ["cleanup_expired_artifacts", "emit_metrics_snapshot", "reset_daily_credits_task"]
