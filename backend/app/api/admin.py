"""Admin routes (SRS ADMIN-001..007, MON, STORAGE-006, RECON-008).

All ``/api/v1/admin/*`` routes sit behind the existing ``require_admin``
dependency (SEC-009). Mutating actions write an audit row (ADMIN-006) via the
service layer so the audit trail stays consistent with the action.

Worker heartbeats are read from Redis (``workers:heartbeat`` hash written by
``workers/common.py``); everything else is DB-backed through the admin repo.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.models import JobType, User, UserRole
from app.repositories import admin as admin_repo
from app.schemas.admin import (
    AbuseActionRequest,
    AbuseActionResponse,
    AbuseReportSummary,
    AdminJob,
    AdminOverview,
    AdminUser,
    AuditEntry,
    JobActionRequest,
    JobActionResponse,
    SystemConfig,
    SystemConfigUpdate,
    UserActionRequest,
    UserActionResponse,
    WorkerInfo,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


def _heartbeats() -> dict[str, int]:
    """Read the Redis heartbeat hash. Tolerates Redis being down — an empty
    dict just means workers fall back to their DB-recorded last_heartbeat."""
    try:
        import redis as _redis_mod

        r = _redis_mod.from_url(settings.redis_url)
        raw = r.hgetall("workers:heartbeat") or {}
        return {k.decode(): int(v) for k, v in raw.items()} if raw else {}
    except Exception:  # noqa: BLE001 — Redis optional on the dev box
        return {}


# --- ADMIN-001 overview ---


@router.get("/overview", response_model=AdminOverview)
def get_overview(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminOverview:
    data = admin_service.get_overview(db, _heartbeats())
    return AdminOverview(**data)


# --- ADMIN-002 users ---


@router.get("/users", response_model=list[AdminUser])
def list_users(
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[AdminUser]:
    rows = admin_repo.list_users(db, q=q)
    out: list[AdminUser] = []
    for u in rows:
        projects, jobs = admin_repo.usage_counts(db, u.id)
        out.append(AdminUser(
            id=u.id, email=u.email, full_name=u.full_name,
            role=u.role.value, account_status=u.account_status.value,
            email_verified=u.email_verified, created_at=u.created_at,
            project_count=projects, job_count=jobs,
        ))
    return out


@router.post("/users/{user_id}", response_model=UserActionResponse)
def act_on_user(
    user_id: str,
    body: UserActionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserActionResponse:
    target = db.get(User, user_id)
    if target is None:
        raise AppError("NOT_FOUND", "User not found.", 404)
    if target.role == UserRole.admin:
        raise AppError("CONFLICT", "Cannot suspend an admin.", 409)
    admin_service.apply_user_action(db, admin=admin, target=target, action=body.action)
    db.commit()
    return UserActionResponse(id=target.id, account_status=target.account_status.value)


# --- ADMIN-003 jobs ---


@router.get("/jobs", response_model=list[AdminJob])
def list_jobs(
    status: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[AdminJob]:
    rows = admin_repo.list_jobs(db, status=status, user_id=user_id, q=q)
    return [AdminJob.model_validate(r) for r in rows]


@router.post("/jobs/{job_id}", response_model=JobActionResponse)
def act_on_job(
    job_id: str,
    body: JobActionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> JobActionResponse:
    job = admin_repo.get_job(db, job_id)
    if job is None:
        raise AppError("NOT_FOUND", "Job not found.", 404)
    admin_service.apply_job_action(db, admin=admin, job=job, action=body.action)
    db.commit()
    # Re-enqueue on retry so the worker picks it back up.
    if body.action == "retry" and job.status.value == "created":
        _reenqueue(job)
    return JobActionResponse(id=job.id, status=job.status.value)


def _reenqueue(job) -> None:
    """Dispatch the job to the matching Celery queue based on its type."""
    # Import workers.celery_app first so the @shared_task binds to our app
    # (broker_url/queues); see app/api/processing.py for the rationale.
    import workers.celery_app  # noqa: F401
    if job.job_type == JobType.process:
        from workers.tasks.processing import process_video
        process_video.apply_async(args=(job.id, job.project_id), queue="processing")
    elif job.job_type == JobType.analyze:
        from workers.tasks.detection import analyze_video
        analyze_video.apply_async(args=(job.id, job.project_id), queue="detection")


@router.delete("/jobs/{job_id}/temp", response_model=dict)
def delete_job_temp_files(
    job_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    """ADMIN-003: delete temp frames/preview artifacts for a job. The isolated
    tempdir is already cleaned on task exit; this clears any persisted frames
    bucket entries the worker wrote for this job."""
    job = admin_repo.get_job(db, job_id)
    if job is None:
        raise AppError("NOT_FOUND", "Job not found.", 404)
    deleted = _clear_job_artifacts(job)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="job.delete_temp",
        target_type="job", target_id=job.id,
        details=admin_service.audit_details("job.delete_temp", deleted=deleted),
    )
    db.commit()
    return {"deleted": deleted}


def _clear_job_artifacts(job) -> int:
    """Best-effort removal of any frames/ directory written for this job. The
    storage backend owns the bucket layout; we just attempt the delete and
    count successes."""
    from app.storage import get_storage

    storage = get_storage()
    count = 0
    prefix = f"{job.project_id}/{job.id}"
    for bucket in ("frames", "previews"):
        try:
            # LocalFs has no list; rely on the key convention. MinIO would
            # use a prefix listing — left as a follow-up since the dev box
            # runs LocalFs.
            storage.delete(bucket, prefix)
            count += 1
        except Exception:  # noqa: BLE001 — cleanup is best-effort
            pass
    return count


# --- ADMIN-004 workers ---


@router.get("/workers", response_model=list[WorkerInfo])
def list_workers(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[WorkerInfo]:
    return admin_service.get_workers(db, _heartbeats())


# --- ADMIN-005 system config ---


@router.get("/config", response_model=SystemConfig)
def get_config(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> SystemConfig:
    overrides = admin_repo.get_all_settings(db)
    return admin_service.build_config(settings, overrides)


@router.patch("/config", response_model=SystemConfig)
def update_config(
    body: SystemConfigUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> SystemConfig:
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise AppError("VALIDATION_ERROR", "No fields supplied.", 422)
    for key, value in changes.items():
        if key not in admin_service.ALL_CONFIG_KEYS:
            raise AppError("VALIDATION_ERROR", f"Unknown config key: {key}", 422)
        admin_repo.upsert_setting(db, key, admin_service.config_value_to_str(key, value))
    admin_repo.record_audit(
        db, actor_id=admin.id, action="config.update",
        target_type="system_settings", target_id=None,
        details=admin_service.audit_details("config.update", **{
            k: (list(v) if isinstance(v, list) else v) for k, v in changes.items()
        }),
    )
    db.commit()
    overrides = admin_repo.get_all_settings(db)
    return admin_service.build_config(settings, overrides)


# --- ADMIN-006 audit ---


@router.get("/audit", response_model=list[AuditEntry])
def list_audit(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[AuditEntry]:
    return [AuditEntry.model_validate(r) for r in admin_repo.list_audit(db)]


# --- ADMIN-007 abuse ---


@router.get("/abuse", response_model=list[AbuseReportSummary])
def list_abuse(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[AbuseReportSummary]:
    return [AbuseReportSummary.model_validate(r) for r in admin_repo.list_abuse(db, status=status)]


@router.post("/abuse/{report_id}", response_model=AbuseActionResponse)
def act_on_abuse(
    report_id: str,
    body: AbuseActionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AbuseActionResponse:
    report = admin_repo.get_abuse(db, report_id)
    if report is None:
        raise AppError("NOT_FOUND", "Abuse report not found.", 404)
    admin_service.apply_abuse_action(db, admin=admin, report=report, action=body.action)
    db.commit()
    return AbuseActionResponse(id=report.id, status=report.status)


__all__ = ["router"]
