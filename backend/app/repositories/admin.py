"""Admin repository (SRS ADMIN-001..007).

Thin data-access layer for the Phase 8 admin surface. Keeps the SQL in one
place so the route layer stays declarative and the aggregates are testable.
Reads are intentionally count/aggregate-based — admin dashboards don't need
to hydrate full ORM rows to render a metric.

Heartbeats come from Redis (``workers/common.py`` writes ``workers:heartbeat``);
worker rows come from the ``worker_nodes`` table. ``list_workers`` fuses the
two so ADMIN-004 shows online/offline + GPU + active job in one payload.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AbuseReport,
    AccountStatus,
    AuditLog,
    JobState,
    JobType,
    OutputFile,
    ProcessingJob,
    SystemSetting,
    User,
    VideoProject,
    WorkerNode,
)


# --- ADMIN-001 overview ---


def _start_of_day_utc() -> datetime:
    n = datetime.now(timezone.utc)
    return n.replace(hour=0, minute=0, second=0, microsecond=0)


def overview_counts(db: Session) -> dict[str, Any]:
    """Aggregate the ADMIN-001 metrics in as few round-trips as possible."""
    total_users = db.execute(select(func.count(User.id))).scalar() or 0
    active_users = db.execute(
        select(func.count(User.id)).where(User.account_status == AccountStatus.active)
    ).scalar() or 0
    suspended_users = db.execute(
        select(func.count(User.id)).where(User.account_status == AccountStatus.suspended)
    ).scalar() or 0

    day_start = _start_of_day_utc()
    jobs_today = db.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.created_at >= day_start)
    ).scalar() or 0
    completed_jobs = db.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.status == JobState.completed)
    ).scalar() or 0
    failed_jobs = db.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.status == JobState.failed)
    ).scalar() or 0

    # Average processing wall-time for completed jobs with both timestamps.
    avg_seconds = db.execute(
        select(func.avg(
            func.extract("epoch", ProcessingJob.completed_at - ProcessingJob.started_at)
        )).where(
            ProcessingJob.status == JobState.completed,
            ProcessingJob.started_at.is_not(None),
            ProcessingJob.completed_at.is_not(None),
        )
    ).scalar()
    avg_seconds = float(avg_seconds) if avg_seconds is not None else None

    return {
        "total_users": int(total_users),
        "active_users": int(active_users),
        "suspended_users": int(suspended_users),
        "jobs_today": int(jobs_today),
        "completed_jobs": int(completed_jobs),
        "failed_jobs": int(failed_jobs),
        "avg_processing_seconds": avg_seconds,
    }


def queue_length(db: Session) -> int:
    """Jobs sitting in a queued state — the pending Celery backlog."""
    queued = (JobState.created, JobState.processing_queued, JobState.preview_queued)
    return int(
        db.execute(
            select(func.count(ProcessingJob.id)).where(ProcessingJob.status.in_(queued))
        ).scalar() or 0
    )


def gpu_worker_count(db: Session) -> int:
    return int(
        db.execute(
            select(func.count(WorkerNode.id)).where(WorkerNode.gpu_name.is_not(None))
        ).scalar() or 0
    )


def storage_bytes(db: Session) -> int:
    """Sum of stored output sizes. Other buckets (original/proxy/frames) are
    GC'd by the retention task; output is the durable footprint worth surfacing."""
    return int(db.execute(select(func.coalesce(func.sum(OutputFile.file_size), 0))).scalar() or 0)


# --- ADMIN-002 users ---


def list_users(db: Session, *, q: str | None = None, limit: int = 100) -> list[User]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(User.email.ilike(like) | User.full_name.ilike(like))
    return list(db.execute(stmt).scalars())


def set_account_status(db: Session, user: User, status: AccountStatus) -> User:
    user.account_status = status
    db.flush()
    return user


def usage_counts(db: Session, user_id: str) -> tuple[int, int]:
    """(project_count, job_count) for the ADMIN-002 usage summary."""
    projects = db.execute(
        select(func.count(VideoProject.id)).where(VideoProject.user_id == user_id)
    ).scalar() or 0
    jobs = db.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.user_id == user_id)
    ).scalar() or 0
    return int(projects), int(jobs)


# --- ADMIN-003 jobs ---


def list_jobs(
    db: Session,
    *,
    status: str | None = None,
    user_id: str | None = None,
    q: str | None = None,
    limit: int = 100,
) -> list[ProcessingJob]:
    stmt = select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(ProcessingJob.status == status)
    if user_id:
        stmt = stmt.where(ProcessingJob.user_id == user_id)
    if q:
        # search by job id prefix — admin incident triage
        stmt = stmt.where(ProcessingJob.id.ilike(f"%{q}%"))
    return list(db.execute(stmt).scalars())


def get_job(db: Session, job_id: str) -> ProcessingJob | None:
    return db.get(ProcessingJob, job_id)


# --- ADMIN-004 workers ---


def list_worker_nodes(db: Session) -> list[WorkerNode]:
    return list(db.execute(select(WorkerNode).order_by(WorkerNode.name.asc())).scalars())


def upsert_worker_heartbeat(
    db: Session, *, name: str, status: str = "idle", **fields: Any
) -> WorkerNode:
    """Idempotent heartbeat upsert — workers call this on startup + each tick."""
    row = db.execute(select(WorkerNode).where(WorkerNode.name == name)).scalars().first()
    now = datetime.now(timezone.utc)
    if row is None:
        row = WorkerNode(name=name, status=status, last_heartbeat=now, **fields)
        db.add(row)
    else:
        row.last_heartbeat = now
        row.status = status
        for k, v in fields.items():
            setattr(row, k, v)
    db.flush()
    return row


def worker_offline_threshold_seconds() -> int:
    """A worker is offline if its heartbeat is older than this. SRS ADMIN-004 +
    MON-002 (worker-offline alert). Mirrors
    ``admin_service.WORKER_OFFLINE_THRESHOLD_SECONDS`` so the pure helper and
    the repo layer agree on one value."""
    from app.services.admin_service import WORKER_OFFLINE_THRESHOLD_SECONDS

    return WORKER_OFFLINE_THRESHOLD_SECONDS


# --- ADMIN-005 system config ---


def get_all_settings(db: Session) -> dict[str, str]:
    """Load the SystemSetting override rows as a flat dict."""
    rows = db.execute(select(SystemSetting)).scalars().all()
    return {r.key: r.value for r in rows}


def upsert_setting(db: Session, key: str, value: str) -> SystemSetting:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalars().first()
    if row is None:
        row = SystemSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.flush()
    return row


# --- ADMIN-006 audit ---


def record_audit(
    db: Session,
    *,
    actor_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.add(row)
    db.flush()
    return row


def list_audit(db: Session, *, limit: int = 100) -> list[AuditLog]:
    return list(
        db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).scalars()
    )


# --- ADMIN-007 abuse ---


def list_abuse(db: Session, *, status: str | None = None, limit: int = 100) -> list[AbuseReport]:
    stmt = select(AbuseReport).order_by(AbuseReport.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(AbuseReport.status == status)
    return list(db.execute(stmt).scalars())


def get_abuse(db: Session, report_id: str) -> AbuseReport | None:
    return db.get(AbuseReport, report_id)


def set_abuse_status(db: Session, report: AbuseReport, status: str) -> AbuseReport:
    report.status = status
    db.flush()
    return report


__all__ = [
    "overview_counts",
    "queue_length",
    "gpu_worker_count",
    "storage_bytes",
    "list_users",
    "set_account_status",
    "usage_counts",
    "list_jobs",
    "get_job",
    "list_worker_nodes",
    "upsert_worker_heartbeat",
    "worker_offline_threshold_seconds",
    "get_all_settings",
    "upsert_setting",
    "record_audit",
    "list_audit",
    "list_abuse",
    "get_abuse",
    "set_abuse_status",
]
