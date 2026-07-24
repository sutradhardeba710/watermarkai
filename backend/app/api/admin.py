"""Admin routes (SRS ADMIN-001..007, MON, STORAGE-006, RECON-008 + PRD Phases 1+2).

All ``/api/v1/admin/*`` routes sit behind ``require_permission`` (PRD §33.1) —
the RBAC map lives in ``app.services.admin_permissions``. Mutating actions
write an audit row (ADMIN-006 / PRD §27) with previous/new values + request
context via the service layer so the audit trail stays consistent with the
action.

Worker heartbeats are read from Redis (``workers:heartbeat`` hash written by
``workers/common.py``); everything else is DB-backed through the admin repo.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin, require_permission
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError
from app.models import JobType, User, AccountStatus, UserRole
from app.repositories import admin as admin_repo
from app.schemas.admin import (
    USER_DELETE_ACTIONS,
    USER_MANAGE_ACTIONS,
    USER_SUPPORT_ACTIONS,
    AbuseActionRequest,
    AbuseActionResponse,
    AbuseReportDetail,
    AbuseReportPage,
    AbuseReportSummary,
    AbuseSeverityRequest,
    AdminJob,
    AdminJobDetail,
    AdminMe,
    AdminOverview,
    AdminProject,
    AdminProjectDetail,
    AdminProjectPage,
    AdminSessionOut,
    AdminUser,
    AdminUserActionRequest,
    AdminUserDetail,
    AdminUserPage,
    AuditEntry,
    AuditPage,
    BillingOverviewOut,
    CreditAdjustRequest,
    CreditDashboardOut,
    CreditTransactionOut,
    CreditTxnPage,
    JobActionRequest,
    JobActionResponse,
    AdminSubscriptionListItem,
    AdminSubscriptionPage,
    PaymentDetailOut,
    PaymentListItem,
    PaymentNoteRequest,
    PaymentOut,
    PaymentPage,
    PlanChangeRequest,
    PlanCreateRequest,
    PlanOut,
    PlanUpdateRequest,
    ProjectActionRequest,
    ProjectActionResponse,
    PromoCreateRequest,
    PromoOut,
    PromoUpdateRequest,
    ComplianceActionRequest,
    ComplianceActionResponse,
    ComplianceOverviewOut,
    RetentionItem,
    RetentionPage,
    StorageActionRequest,
    StorageActionResponse,
    StorageOverviewOut,
    QueueMetrics,
    AIModelOut,
    AIModelCreate,
    AIModelUpdate,
    ModelActionRequest,
    PresetOut,
    PresetWrite,
    FeatureFlagOut,
    FeatureFlagUpdate,
    NotificationTemplateOut,
    NotificationTemplateUpdate,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    BroadcastRequest,
    BroadcastResponse,
    MaintenanceState,
    AnalyticsOut,
    ExportRequest,
    SystemHealthOut,
    IncidentOut,
    IncidentCreate,
    IncidentActionRequest,
    AdminListItem,
    AdminMgmtActionRequest,
    AdminInviteRequest,
    GlobalSearchOut,
    SecretsOut,
    RefundOut,
    RefundRequest,
    RoleChangeRequest,
    SubscriptionActionRequest,
    SupportNoteCreate,
    SupportNoteOut,
    SystemConfig,
    SystemConfigUpdate,
    WebhookEventOut,
    WebhookEventPage,
    WorkerDetail,
    WorkerInfo,
)
from app.services import admin_service
from app.services.admin_permissions import effective_admin_role, permissions_for

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


def _audit_ctx(request: Request) -> dict:
    return admin_service.build_audit_context(request)


# --- /admin/me — powers frontend nav gating ---


@router.get("/me", response_model=AdminMe)
def admin_me(admin: User = Depends(get_current_admin)) -> AdminMe:
    role = effective_admin_role(admin.role.value, admin.admin_role)
    return AdminMe(
        id=admin.id, email=admin.email, full_name=admin.full_name,
        admin_role=role or "", permissions=permissions_for(role),
    )


# --- ADMIN-001 overview ---


@router.get("/overview", response_model=AdminOverview)
def get_overview(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("overview.view")),
) -> AdminOverview:
    data = admin_service.get_overview(db, _heartbeats())
    return AdminOverview(**data)


# --- ADMIN-002 / PRD §8 users ---


def _user_row(db: Session, u: User) -> AdminUser:
    projects, jobs = admin_repo.usage_counts(db, u.id)
    return AdminUser(
        id=u.id, email=u.email, full_name=u.full_name,
        role=u.role.value, admin_role=u.admin_role,
        account_status=u.account_status.value,
        email_verified=u.email_verified, created_at=u.created_at,
        plan_id=u.plan_id or "free", credits_remaining=u.credits_remaining,
        project_count=projects, job_count=jobs,
    )


@router.get("/users", response_model=AdminUserPage)
def list_users(
    q: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    plan: Optional[str] = Query(default=None),
    verified: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("users.view")),
) -> AdminUserPage:
    page, page_size, limit, offset = admin_service.paginate(page, page_size)
    rows, total = admin_repo.list_users_paged(
        db, q=q, status=status, role=role, plan_id=plan, verified=verified,
        limit=limit, offset=offset,
    )
    return AdminUserPage(
        items=[_user_row(db, u) for u in rows],
        total=total, page=page, page_size=page_size,
    )


def _get_target_user(db: Session, user_id: str) -> User:
    target = admin_repo.get_user(db, user_id)
    if target is None:
        raise AppError("NOT_FOUND", "User not found.", 404)
    return target


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("users.view")),
) -> AdminUserDetail:
    target = _get_target_user(db, user_id)
    return AdminUserDetail(**admin_service.get_user_detail(db, target))


@router.get("/users/{user_id}/transactions", response_model=CreditTxnPage)
def list_user_transactions(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("users.view")),
) -> CreditTxnPage:
    _get_target_user(db, user_id)
    page, page_size, limit, offset = admin_service.paginate(page, page_size)
    rows, total = admin_repo.list_credit_txns(db, user_id, limit=limit, offset=offset)
    return CreditTxnPage(
        items=[CreditTransactionOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.get("/users/{user_id}/payments", response_model=list[PaymentOut])
def list_user_payments(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("users.view")),
) -> list[PaymentOut]:
    _get_target_user(db, user_id)
    rows, _total = admin_repo.list_payments(db, user_id=user_id, limit=100, offset=0)
    return [PaymentOut.model_validate(r) for r in rows]


@router.get("/users/{user_id}/projects", response_model=list[AdminProject])
def list_user_projects(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("users.view")),
) -> list[AdminProject]:
    target = _get_target_user(db, user_id)
    rows, _total = admin_repo.list_user_projects(db, user_id, limit=100, offset=0)
    return [_project_row(p, target.email) for p in rows]


@router.get("/users/{user_id}/jobs", response_model=list[AdminJob])
def list_user_jobs(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("users.view")),
) -> list[AdminJob]:
    _get_target_user(db, user_id)
    rows = admin_repo.list_jobs(db, user_id=user_id)
    return [AdminJob.model_validate(r) for r in rows]


@router.get("/users/{user_id}/sessions", response_model=list[AdminSessionOut])
def list_user_sessions(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("users.view")),
) -> list[AdminSessionOut]:
    _get_target_user(db, user_id)
    return [AdminSessionOut.model_validate(s) for s in admin_repo.list_user_sessions(db, user_id)]


@router.get("/users/{user_id}/activity", response_model=AuditPage)
def list_user_activity(
    user_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("users.view")),
) -> AuditPage:
    _get_target_user(db, user_id)
    page, page_size, limit, offset = admin_service.paginate(page, page_size)
    rows, total = admin_repo.list_audit_for_user(db, user_id, limit=limit, offset=offset)
    return AuditPage(
        items=[AuditEntry.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


@router.get("/users/{user_id}/notes", response_model=list[SupportNoteOut])
def list_user_notes(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("notes.view")),
) -> list[SupportNoteOut]:
    _get_target_user(db, user_id)
    return [SupportNoteOut.model_validate(n) for n in admin_repo.list_notes(db, user_id=user_id)]


@router.post("/users/{user_id}/notes", response_model=SupportNoteOut)
def create_user_note(
    user_id: str,
    body: SupportNoteCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("notes.manage")),
) -> SupportNoteOut:
    _get_target_user(db, user_id)
    note = admin_repo.insert_note(
        db, user_id=user_id, project_id=body.project_id,
        author_id=admin.id, body=body.body, pinned=body.pinned,
    )
    admin_repo.record_audit(
        db, actor_id=admin.id, action="note.create",
        target_type="user", target_id=user_id,
        details=admin_service.audit_details("note.create", note_id=note.id),
        **_audit_ctx(request),
    )
    db.commit()
    return SupportNoteOut.model_validate(note)


@router.delete("/notes/{note_id}", response_model=dict)
def delete_note(
    note_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("notes.manage")),
) -> dict:
    note = admin_repo.get_note(db, note_id)
    if note is None:
        raise AppError("NOT_FOUND", "Note not found.", 404)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="note.delete",
        target_type="user", target_id=note.user_id,
        details=admin_service.audit_details("note.delete", note_id=note.id),
        **_audit_ctx(request),
    )
    admin_repo.delete_note(db, note)
    db.commit()
    return {"deleted": True}


def _permission_for_user_action(action: str) -> str:
    if action in USER_SUPPORT_ACTIONS:
        return "users.support"
    if action in USER_MANAGE_ACTIONS:
        return "users.manage"
    if action in USER_DELETE_ACTIONS:
        return "users.delete"
    return "users.manage"


@router.post("/users/{user_id}/actions", response_model=dict)
def act_on_user(
    user_id: str,
    body: AdminUserActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> dict:
    # Per-action permission (PRD §5): support actions vs. manage vs. delete.
    from app.services.admin_permissions import has_permission

    role = effective_admin_role(admin.role.value, admin.admin_role)
    if not has_permission(role, _permission_for_user_action(body.action)):
        raise AppError("FORBIDDEN", "Insufficient admin permissions.", 403)
    target = _get_target_user(db, user_id)
    result = admin_service.apply_user_admin_action(
        db, admin=admin, target=target, action=body.action,
        reason=body.reason, audit_ctx=_audit_ctx(request),
    )
    db.commit()
    return {"id": target.id, **result}


@router.post("/users/{user_id}/role", response_model=dict)
def change_user_role(
    user_id: str,
    body: RoleChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("users.role")),
) -> dict:
    target = _get_target_user(db, user_id)
    admin_service.change_admin_role(
        db, admin=admin, target=target, new_role=body.admin_role,
        audit_ctx=_audit_ctx(request),
    )
    db.commit()
    return {"id": target.id, "admin_role": target.admin_role}


@router.post("/users/{user_id}/plan", response_model=dict)
def change_user_plan(
    user_id: str,
    body: PlanChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("users.plan")),
) -> dict:
    target = _get_target_user(db, user_id)
    admin_service.change_plan(
        db, admin=admin, target=target, plan_id=body.plan_id,
        reason=body.reason, audit_ctx=_audit_ctx(request),
    )
    db.commit()
    return {"id": target.id, "plan_id": target.plan_id, "credits_remaining": target.credits_remaining}


@router.post("/users/{user_id}/credits", response_model=dict)
def adjust_user_credits(
    user_id: str,
    body: CreditAdjustRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("users.credits")),
) -> dict:
    target = _get_target_user(db, user_id)
    result = admin_service.adjust_credits(
        db, admin=admin, target=target, amount=body.amount,
        direction=body.direction, reason=body.reason, reference=body.reference,
        audit_ctx=_audit_ctx(request),
    )
    db.commit()
    return {
        "id": target.id,
        "credits_remaining": result["balance"],
        "transaction_id": result["transaction"].id,
    }


# --- PRD §9 projects ---


def _project_row(p, user_email: Optional[str] = None) -> AdminProject:
    return AdminProject(
        id=p.id, user_id=p.user_id, user_email=user_email,
        title=p.title, original_filename=p.original_filename,
        status=p.status.value, duration=p.duration, width=p.width, height=p.height,
        file_size=p.file_size, locked=p.locked, deleted=p.deleted,
        created_at=p.created_at, completed_at=p.completed_at, expires_at=p.expires_at,
    )


@router.get("/projects", response_model=AdminProjectPage)
def list_projects(
    q: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    locked: Optional[bool] = Query(default=None),
    include_deleted: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("projects.view")),
) -> AdminProjectPage:
    page, page_size, limit, offset = admin_service.paginate(page, page_size)
    rows, total = admin_repo.list_projects_paged(
        db, q=q, status=status, user_id=user_id, locked=locked,
        include_deleted=include_deleted, limit=limit, offset=offset,
    )
    return AdminProjectPage(
        items=[_project_row(p, email) for p, email in rows],
        total=total, page=page, page_size=page_size,
    )


def _get_target_project(db: Session, project_id: str):
    project = admin_repo.get_project(db, project_id)
    if project is None:
        raise AppError("NOT_FOUND", "Project not found.", 404)
    return project


@router.get("/projects/{project_id}", response_model=AdminProjectDetail)
def get_project_detail(
    project_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("projects.view")),
) -> AdminProjectDetail:
    p = _get_target_project(db, project_id)
    owner = admin_repo.get_user(db, p.user_id)
    jobs = admin_repo.project_jobs(db, p.id)
    outputs = admin_repo.project_outputs(db, p.id)
    compliance = admin_repo.project_compliance(db, p.id)
    notes = admin_repo.list_notes(db, project_id=p.id)
    base = _project_row(p, owner.email if owner else None).model_dump()
    return AdminProjectDetail(
        **base,
        fps=p.fps, frame_count=p.frame_count,
        video_codec=p.video_codec, audio_codec=p.audio_codec, has_audio=p.has_audio,
        moderation_note=p.moderation_note,
        input_storage_key=p.input_storage_key,
        output_storage_key=p.output_storage_key,
        preview_storage_key=p.preview_storage_key,
        jobs=[AdminJob.model_validate(j) for j in jobs],
        outputs=[{
            "id": o.id, "storage_key": o.storage_key, "bucket": o.bucket,
            "file_size": o.file_size, "quality_mode": o.quality_mode.value,
            "created_at": o.created_at, "expires_at": o.expires_at,
        } for o in outputs],
        compliance=compliance,
        notes=[SupportNoteOut.model_validate(n) for n in notes],
    )


@router.post("/projects/{project_id}/actions", response_model=ProjectActionResponse)
def act_on_project(
    project_id: str,
    body: ProjectActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("projects.manage")),
) -> ProjectActionResponse:
    project = _get_target_project(db, project_id)
    admin_service.apply_project_action(
        db, admin=admin, project=project, action=body.action,
        reason=body.reason, hours=body.hours, audit_ctx=_audit_ctx(request),
    )
    db.commit()
    return ProjectActionResponse(
        id=project.id, status=project.status.value,
        locked=project.locked, expires_at=project.expires_at,
    )


@router.delete("/projects/{project_id}", response_model=dict)
def delete_project(
    project_id: str,
    request: Request,
    reason: str = Query(min_length=3),
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("projects.manage")),
) -> dict:
    """Soft delete + best-effort storage cleanup (PRD §9.5)."""
    project = _get_target_project(db, project_id)
    result = admin_service.apply_project_action(
        db, admin=admin, project=project, action="delete_files",
        reason=reason, audit_ctx=_audit_ctx(request),
    )
    project.deleted = True
    admin_repo.record_audit(
        db, actor_id=admin.id, action="project.delete",
        target_type="project", target_id=project.id,
        details=admin_service.audit_details("project.delete", user_id=project.user_id),
        reason=reason,
        **_audit_ctx(request),
    )
    db.commit()
    return {"id": project.id, "deleted": True, "deleted_files": result["deleted_files"]}


# --- ADMIN-003 jobs ---


@router.get("/jobs", response_model=list[AdminJob])
def list_jobs(
    status: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("jobs.view")),
) -> list[AdminJob]:
    rows = admin_repo.list_jobs(db, status=status, user_id=user_id, q=q)
    return [AdminJob.model_validate(r) for r in rows]


def _job_seconds(job) -> tuple[Optional[float], Optional[float]]:
    """(duration_seconds, queued_seconds) for a job — wall time running and
    time spent waiting before a worker picked it up."""
    duration = None
    if job.started_at and job.completed_at:
        duration = (job.completed_at - job.started_at).total_seconds()
    queued = None
    if job.created_at and job.started_at:
        queued = (job.started_at - job.created_at).total_seconds()
    return duration, queued


@router.get("/jobs/{job_id}", response_model=AdminJobDetail)
def get_job_detail(
    job_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("jobs.view")),
) -> AdminJobDetail:
    """Incident bundle for one job: stage timeline + timing + recent audit
    events (PRD §10.3)."""
    job = admin_repo.get_job(db, job_id)
    if job is None:
        raise AppError("NOT_FOUND", "Job not found.", 404)
    project = admin_repo.get_project(db, job.project_id)
    owner = admin_repo.get_user(db, job.user_id)
    duration, queued = _job_seconds(job)
    timeline = admin_service.job_stage_timeline(job.job_type.value, job.status.value)
    events = admin_repo.list_audit_for_target(db, "job", job.id, limit=20)
    base = AdminJob.model_validate(job).model_dump()
    return AdminJobDetail(
        **base,
        project_title=project.title if project else None,
        user_email=owner.email if owner else None,
        duration_seconds=duration,
        queued_seconds=queued,
        timeline=timeline,
        recent_events=[AuditEntry.model_validate(e) for e in events],
    )


@router.post("/jobs/{job_id}", response_model=JobActionResponse)
def act_on_job(
    job_id: str,
    body: JobActionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("jobs.manage")),
) -> JobActionResponse:
    job = admin_repo.get_job(db, job_id)
    if job is None:
        raise AppError("NOT_FOUND", "Job not found.", 404)
    admin_service.apply_job_action(db, admin=admin, job=job, action=body.action)
    db.commit()
    # Re-enqueue on retry so the worker picks it back up.
    if body.action == "retry" and job.status.value == "processing_queued":
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
    admin: User = Depends(require_permission("jobs.manage")),
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


@router.get("/queues", response_model=QueueMetrics)
def get_queues(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("jobs.view")),
) -> QueueMetrics:
    """Queue depth + throughput dashboard (PRD §11). Reads DB-derived depth so
    it works whether or not the Celery inspect API is reachable."""
    metrics = admin_repo.queue_metrics(db)
    metrics["queues"] = admin_repo.queue_breakdown(db)
    return QueueMetrics(**metrics)


@router.get("/workers", response_model=list[WorkerInfo])
def list_workers(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("workers.view")),
) -> list[WorkerInfo]:
    return admin_service.get_workers(db, _heartbeats())


@router.get("/workers/{worker_name}", response_model=WorkerDetail)
def get_worker_detail(
    worker_name: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("workers.view")),
) -> WorkerDetail:
    """Per-worker deep-dive: fused online state + its recent job history and
    lifetime completed/failed counts (PRD §12.3)."""
    node = admin_repo.get_worker_node(db, worker_name)
    if node is None:
        raise AppError("NOT_FOUND", "Worker not found.", 404)
    fused = admin_service.fuse_workers([node], _heartbeats())[0]
    recent = admin_repo.worker_jobs(db, worker_name, limit=25)
    completed, failed = admin_repo.worker_job_counts(db, worker_name)
    active_job = None
    if node.active_job_id:
        job = admin_repo.get_job(db, node.active_job_id)
        if job is not None:
            active_job = AdminJob.model_validate(job)
    return WorkerDetail(
        **fused.model_dump(),
        active_job=active_job,
        recent_jobs=[AdminJob.model_validate(j) for j in recent],
        completed_count=completed,
        failed_count=failed,
    )


# --- ADMIN-005 system config ---


@router.get("/config", response_model=SystemConfig)
def get_config(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("config.view")),
) -> SystemConfig:
    overrides = admin_repo.get_all_settings(db)
    return admin_service.build_config(settings, overrides)


@router.patch("/config", response_model=SystemConfig)
def update_config(
    body: SystemConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("config.manage")),
) -> SystemConfig:
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise AppError("VALIDATION_ERROR", "No fields supplied.", 422)
    previous = admin_repo.get_all_settings(db)
    for key, value in changes.items():
        if key not in admin_service.ALL_CONFIG_KEYS:
            raise AppError("VALIDATION_ERROR", f"Unknown config key: {key}", 422)
        admin_repo.upsert_setting(db, key, admin_service.config_value_to_str(key, value))
    admin_repo.record_audit(
        db, actor_id=admin.id, action="config.update",
        target_type="system_settings", target_id=None,
        details=admin_service.audit_details("config.update", keys=sorted(changes.keys())),
        previous_data={k: previous.get(k) for k in changes},
        new_data={k: (list(v) if isinstance(v, list) else v) for k, v in changes.items()},
        **_audit_ctx(request),
    )
    db.commit()
    overrides = admin_repo.get_all_settings(db)
    return admin_service.build_config(settings, overrides)


# --- ADMIN-006 audit ---


@router.get("/audit", response_model=AuditPage)
def list_audit(
    action: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    target_type: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("audit.view")),
) -> AuditPage:
    page, page_size, limit, offset = admin_service.paginate(page, page_size)
    rows, total = admin_repo.list_audit_filtered(
        db, action=action, actor_id=actor_id, target_type=target_type,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset,
    )
    return AuditPage(
        items=[AuditEntry.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


# --- ADMIN-007 abuse ---


@router.get("/abuse", response_model=list[AbuseReportSummary])
def list_abuse(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("abuse.view")),
) -> list[AbuseReportSummary]:
    return [AbuseReportSummary.model_validate(r) for r in admin_repo.list_abuse(db, status=status)]


@router.post("/abuse/{report_id}", response_model=AbuseActionResponse)
def act_on_abuse(
    report_id: str,
    body: AbuseActionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("abuse.manage")),
) -> AbuseActionResponse:
    report = admin_repo.get_abuse(db, report_id)
    if report is None:
        raise AppError("NOT_FOUND", "Abuse report not found.", 404)
    admin_service.apply_abuse_action(db, admin=admin, report=report, action=body.action)
    db.commit()
    return AbuseActionResponse(id=report.id, status=report.status)


# =====================================================================
# Admin Panel Phase 4 — billing / payments / subscriptions / plans /
# promos / credits (PRD §13–17). Gateway identifiers are masked before
# leaving the server (PRD §13.4, §33.2). Every mutation writes an audit
# row + commit. Direct credit-balance edits are forbidden — all credit
# movement flows through the ledger (PRD §17.4).
# =====================================================================


def _actor_role(admin: User) -> str:
    return effective_admin_role(admin.role.value, admin.admin_role) or ""


def _user_email(db: Session, user_id: str) -> Optional[str]:
    u = admin_repo.get_user(db, user_id)
    return u.email if u else None


def _payment_list_item(payment, email: Optional[str]) -> PaymentListItem:
    return PaymentListItem(
        id=payment.id, user_id=payment.user_id, user_email=email,
        plan_id=payment.plan_id, amount_inr=payment.amount_inr,
        currency=payment.currency, status=payment.status, method=payment.method,
        razorpay_payment_id=admin_service.mask_secret(payment.razorpay_payment_id),
        promo_code=payment.promo_code, refund_status=payment.refund_status,
        refunded_inr=payment.refunded_inr, manual_review=payment.manual_review,
        created_at=payment.created_at,
    )


def _refund_out(r) -> RefundOut:
    return RefundOut(
        id=r.id, payment_id=r.payment_id, user_id=r.user_id, amount_inr=r.amount_inr,
        kind=r.kind, reason=r.reason,
        razorpay_refund_id=admin_service.mask_secret(r.razorpay_refund_id),
        status=r.status, admin_id=r.admin_id, created_at=r.created_at,
    )


# --- PRD §13.1 billing dashboard ---


@router.get("/billing", response_model=BillingOverviewOut)
def billing_overview(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("billing.view")),
) -> BillingOverviewOut:
    counts = admin_repo.billing_counts(db)
    active = admin_repo.active_subscription_count(db)
    return BillingOverviewOut(**admin_service.billing_overview(counts, active_subscriptions=active))


# --- PRD §13.3 payments list + detail ---


@router.get("/payments", response_model=PaymentPage)
def list_payments(
    status: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("billing.view")),
) -> PaymentPage:
    page, page_size, limit, offset = admin_service.paginate(page, page_size)
    rows, total = admin_repo.list_payments_filtered(
        db, status=status, user_id=user_id, q=q, limit=limit, offset=offset
    )
    return PaymentPage(
        items=[_payment_list_item(p, email) for p, email in rows],
        total=total, page=page, page_size=page_size,
    )


@router.get("/payments/{payment_id}", response_model=PaymentDetailOut)
def get_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("billing.view")),
) -> PaymentDetailOut:
    payment = admin_repo.get_payment(db, payment_id)
    if payment is None:
        raise AppError("NOT_FOUND", "Payment not found.", 404)
    refunded = admin_repo.total_refunded(db, payment_id)
    refunds = admin_repo.list_refunds(db, payment_id)
    email = _user_email(db, payment.user_id)
    return PaymentDetailOut(
        id=payment.id, user_id=payment.user_id, user_email=email,
        subscription_id=payment.subscription_id, plan_id=payment.plan_id,
        amount_inr=payment.amount_inr, currency=payment.currency, status=payment.status,
        method=payment.method, description=payment.description,
        discount_inr=payment.discount_inr, tax_inr=payment.tax_inr,
        credits_issued=payment.credits_issued, promo_code=payment.promo_code,
        razorpay_payment_id=admin_service.mask_secret(payment.razorpay_payment_id),
        razorpay_order_id=admin_service.mask_secret(payment.razorpay_order_id),
        razorpay_subscription_id=admin_service.mask_secret(payment.razorpay_subscription_id),
        captured_at=payment.captured_at, failure_reason=payment.failure_reason,
        refund_status=payment.refund_status or admin_service.refund_status_after(payment.amount_inr, refunded),
        refunded_inr=refunded, refundable_inr=max(0, payment.amount_inr - refunded),
        manual_review=payment.manual_review, internal_note=payment.internal_note,
        created_at=payment.created_at, refunds=[_refund_out(r) for r in refunds],
    )


@router.post("/payments/{payment_id}/refund", response_model=RefundOut)
def refund_payment(
    payment_id: str,
    body: RefundRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("billing.manage")),
) -> RefundOut:
    payment = admin_repo.get_payment(db, payment_id)
    if payment is None:
        raise AppError("NOT_FOUND", "Payment not found.", 404)
    if payment.status not in ("captured", "partially_refunded"):
        raise AppError("INVALID_STATE", "Only captured payments can be refunded.", 409)
    already = admin_repo.total_refunded(db, payment_id)
    # PRD §13.5 — validate the amount against the refundable balance.
    try:
        kind = admin_service.validate_refund(
            amount_inr=body.amount_inr,
            payment_amount_inr=payment.amount_inr,
            already_refunded_inr=already,
        )
    except ValueError as exc:
        raise AppError("INVALID_AMOUNT", str(exc), 422) from exc
    # PRD §13.5 — high-value refunds require a super-admin actor.
    if admin_service.refund_requires_approval(body.amount_inr, actor_role=_actor_role(admin)):
        raise AppError(
            "APPROVAL_REQUIRED",
            "Refunds at or above the threshold require super-admin approval.",
            403,
        )
    refund = admin_repo.insert_refund(
        db, payment_id=payment_id, user_id=payment.user_id,
        amount_inr=body.amount_inr, kind=kind, reason=body.reason, admin_id=admin.id,
    )
    new_total = already + body.amount_inr
    previous_status = payment.status  # capture before mutation for the audit trail
    payment.refunded_inr = new_total
    payment.refund_status = admin_service.refund_status_after(payment.amount_inr, new_total)
    if payment.refund_status == "full":
        payment.status = "refunded"
    elif payment.refund_status == "partial":
        payment.status = "partially_refunded"
    admin_repo.record_audit(
        db, actor_id=admin.id, action="payment.refund",
        target_type="payment", target_id=payment_id,
        previous_data={"refunded_inr": already, "status": previous_status},
        new_data={"refunded_inr": new_total, "status": payment.status, "kind": kind, "amount_inr": body.amount_inr},
        reason=body.reason, **_audit_ctx(request),
    )
    db.commit()
    return _refund_out(refund)


@router.post("/payments/{payment_id}/note", response_model=PaymentDetailOut)
def update_payment_note(
    payment_id: str,
    body: PaymentNoteRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("billing.manage")),
) -> PaymentDetailOut:
    payment = admin_repo.get_payment(db, payment_id)
    if payment is None:
        raise AppError("NOT_FOUND", "Payment not found.", 404)
    prev = {"internal_note": payment.internal_note, "manual_review": payment.manual_review}
    if body.internal_note is not None:
        payment.internal_note = body.internal_note
    if body.manual_review is not None:
        payment.manual_review = body.manual_review
    admin_repo.record_audit(
        db, actor_id=admin.id, action="payment.note",
        target_type="payment", target_id=payment_id,
        previous_data=prev,
        new_data={"internal_note": payment.internal_note, "manual_review": payment.manual_review},
        **_audit_ctx(request),
    )
    db.commit()
    return get_payment(payment_id, db=db, _admin=admin)


# --- PRD §13.4 / §26 webhook events viewer ---


@router.get("/webhooks", response_model=WebhookEventPage)
def list_webhooks(
    event_type: Optional[str] = Query(default=None),
    payment_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("billing.view")),
) -> WebhookEventPage:
    page, page_size, limit, offset = admin_service.paginate(page, page_size)
    rows, total = admin_repo.list_webhook_events(
        db, event_type=event_type, payment_id=payment_id, limit=limit, offset=offset
    )
    # List view omits the raw payload (PRD §13.4 — masked/detail-only).
    items = [
        WebhookEventOut(
            id=e.id, event_type=e.event_type,
            razorpay_event_id=admin_service.mask_secret(e.razorpay_event_id),
            payment_id=e.payment_id, subscription_ref=e.subscription_ref,
            signature_valid=e.signature_valid, status=e.status, result=e.result,
            created_at=e.created_at, payload=None,
        )
        for e in rows
    ]
    return WebhookEventPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/webhooks/{event_id}", response_model=WebhookEventOut)
def get_webhook(
    event_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("billing.view")),
) -> WebhookEventOut:
    e = admin_repo.get_webhook_event(db, event_id)
    if e is None:
        raise AppError("NOT_FOUND", "Webhook event not found.", 404)
    return WebhookEventOut(
        id=e.id, event_type=e.event_type,
        razorpay_event_id=admin_service.mask_secret(e.razorpay_event_id),
        payment_id=e.payment_id, subscription_ref=e.subscription_ref,
        signature_valid=e.signature_valid, status=e.status, result=e.result,
        created_at=e.created_at,
        payload=admin_service.mask_webhook_payload(e.payload),
    )


# --- PRD §14 subscriptions ---


def _subscription_item(sub, email: Optional[str]) -> AdminSubscriptionListItem:
    status = sub.status.value if hasattr(sub.status, "value") else str(sub.status)
    return AdminSubscriptionListItem(
        id=sub.id, user_id=sub.user_id, user_email=email, plan_id=sub.plan_id,
        status=status,
        display_status=admin_service.subscription_display_status(
            status, cancel_at_period_end=sub.cancel_at_period_end, grace_until=sub.grace_until,
        ),
        cancel_at_period_end=sub.cancel_at_period_end, payment_failures=sub.payment_failures,
        current_period_start=sub.current_period_start, current_period_end=sub.current_period_end,
        grace_until=sub.grace_until, cancelled_at=sub.cancelled_at, created_at=sub.created_at,
    )


@router.get("/subscriptions", response_model=AdminSubscriptionPage)
def list_subscriptions(
    status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("billing.view")),
) -> AdminSubscriptionPage:
    page, page_size, limit, offset = admin_service.paginate(page, page_size)
    rows, total = admin_repo.list_subscriptions(db, status=status, limit=limit, offset=offset)
    return AdminSubscriptionPage(
        items=[_subscription_item(s, email) for s, email in rows],
        total=total, page=page, page_size=page_size,
    )


@router.post("/subscriptions/{subscription_id}/actions", response_model=AdminSubscriptionListItem)
def subscription_action(
    subscription_id: str,
    body: SubscriptionActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("billing.manage")),
) -> AdminSubscriptionListItem:
    sub = admin_repo.get_subscription(db, subscription_id)
    if sub is None:
        raise AppError("NOT_FOUND", "Subscription not found.", 404)
    result = admin_service.apply_subscription_action(
        db, admin=admin, subscription=sub, action=body.action,
        plan_id=body.plan_id, reason=body.reason, audit_ctx=_audit_ctx(request),
    )
    db.commit()
    email = _user_email(db, sub.user_id)
    return _subscription_item(result, email)


# --- PRD §15 plans CRUD ---


def _plan_out(plan, *, subscriber_count: int = 0) -> PlanOut:
    return PlanOut(
        id=plan.id, name=plan.name, description=plan.description,
        price_inr=plan.price_inr, annual_price_inr=plan.annual_price_inr,
        currency=plan.currency, billing_interval=plan.billing_interval,
        credits_per_day=plan.credits_per_day, monthly_credits=plan.monthly_credits,
        razorpay_plan_id=plan.razorpay_plan_id, is_active=plan.is_active,
        archived=plan.archived, is_recommended=plan.is_recommended,
        display_order=plan.display_order, max_upload_mb=plan.max_upload_mb,
        max_duration_seconds=plan.max_duration_seconds, max_resolution=plan.max_resolution,
        concurrent_jobs=plan.concurrent_jobs, storage_allowance_mb=plan.storage_allowance_mb,
        retention_days=plan.retention_days, priority_level=plan.priority_level,
        api_access=plan.api_access, support_level=plan.support_level,
        subscriber_count=subscriber_count, created_at=plan.created_at,
    )


@router.get("/plans", response_model=list[PlanOut])
def list_plans(
    include_archived: bool = Query(default=True),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("billing.view")),
) -> list[PlanOut]:
    plans = admin_repo.list_plans(db, include_archived=include_archived)
    return [_plan_out(p, subscriber_count=admin_repo.plan_subscriber_count(db, p.id)) for p in plans]


@router.post("/plans", response_model=PlanOut)
def create_plan(
    body: PlanCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("plans.manage")),
) -> PlanOut:
    if admin_repo.get_plan(db, body.id) is not None:
        raise AppError("CONFLICT", "A plan with that id already exists.", 409)
    try:
        admin_service.validate_plan_fields(
            price_inr=body.price_inr, credits_per_day=body.credits_per_day,
            billing_interval=body.billing_interval,
        )
    except ValueError as exc:
        raise AppError("INVALID_FIELDS", str(exc), 422) from exc
    plan = admin_repo.insert_plan(db, **body.model_dump())
    admin_repo.record_audit(
        db, actor_id=admin.id, action="plan.create",
        target_type="plan", target_id=plan.id,
        new_data=body.model_dump(), **_audit_ctx(request),
    )
    db.commit()
    return _plan_out(plan)


@router.patch("/plans/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: str,
    body: PlanUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("plans.manage")),
) -> PlanOut:
    plan = admin_repo.get_plan(db, plan_id)
    if plan is None:
        raise AppError("NOT_FOUND", "Plan not found.", 404)
    changes = body.model_dump(exclude_unset=True, exclude={"reason"})
    prev = {k: getattr(plan, k) for k in changes}
    try:
        admin_service.validate_plan_fields(
            price_inr=changes.get("price_inr", plan.price_inr),
            credits_per_day=changes.get("credits_per_day", plan.credits_per_day),
            billing_interval=changes.get("billing_interval", plan.billing_interval),
        )
    except ValueError as exc:
        raise AppError("INVALID_FIELDS", str(exc), 422) from exc
    for k, v in changes.items():
        setattr(plan, k, v)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="plan.update",
        target_type="plan", target_id=plan.id,
        previous_data=prev, new_data=changes, reason=body.reason, **_audit_ctx(request),
    )
    db.commit()
    return _plan_out(plan, subscriber_count=admin_repo.plan_subscriber_count(db, plan.id))


# --- PRD §16 promo codes CRUD ---


def _promo_out(promo) -> PromoOut:
    return PromoOut(
        id=promo.id, code=promo.code, description=promo.description,
        discount_type=promo.discount_type, discount_value=promo.discount_value,
        discount_percent=promo.discount_percent, max_discount_inr=promo.max_discount_inr,
        applicable_plans=promo.applicable_plans, is_active=promo.is_active,
        sandbox_only=promo.sandbox_only, new_users_only=promo.new_users_only,
        min_purchase_inr=promo.min_purchase_inr, starts_at=promo.starts_at, ends_at=promo.ends_at,
        max_total_uses=promo.max_total_uses, max_uses_per_user=promo.max_uses_per_user,
        times_redeemed=promo.times_redeemed,
        remaining_uses=admin_service.promo_remaining_uses(promo.max_total_uses, promo.times_redeemed),
        razorpay_offer_id=promo.razorpay_offer_id, created_at=promo.created_at,
    )


@router.get("/promos", response_model=list[PromoOut])
def list_promos(
    active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("billing.view")),
) -> list[PromoOut]:
    return [_promo_out(p) for p in admin_repo.list_promos(db, active=active)]


@router.post("/promos", response_model=PromoOut)
def create_promo(
    body: PromoCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("promos.manage")),
) -> PromoOut:
    code = body.code.strip().upper()
    if admin_repo.get_promo_by_code(db, code) is not None:
        raise AppError("CONFLICT", "A promo with that code already exists.", 409)
    try:
        admin_service.validate_promo_fields(
            discount_type=body.discount_type, discount_value=body.discount_value,
            max_total_uses=body.max_total_uses, max_uses_per_user=body.max_uses_per_user,
        )
    except ValueError as exc:
        raise AppError("INVALID_FIELDS", str(exc), 422) from exc
    # PRD §16.4 — SANDBOX-only promos cannot be enabled in production.
    if body.sandbox_only and settings.environment in ("prod", "production"):
        raise AppError("FORBIDDEN", "Sandbox-only promos cannot be created in production.", 403)
    fields = body.model_dump()
    fields["code"] = code
    # discount_percent is the legacy column; mirror percentage discounts into it.
    fields["discount_percent"] = body.discount_value if body.discount_type == "percentage" else 0
    promo = admin_repo.insert_promo(db, **fields)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="promo.create",
        target_type="promo", target_id=promo.id,
        new_data={**fields, "code": code}, **_audit_ctx(request),
    )
    db.commit()
    return _promo_out(promo)


@router.patch("/promos/{promo_id}", response_model=PromoOut)
def update_promo(
    promo_id: str,
    body: PromoUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("promos.manage")),
) -> PromoOut:
    promo = admin_repo.get_promo(db, promo_id)
    if promo is None:
        raise AppError("NOT_FOUND", "Promo not found.", 404)
    changes = body.model_dump(exclude_unset=True, exclude={"reason"})
    if "discount_type" in changes or "discount_value" in changes:
        admin_service.validate_promo_fields(
            discount_type=changes.get("discount_type", promo.discount_type),
            discount_value=changes.get("discount_value", promo.discount_value),
            max_total_uses=changes.get("max_total_uses", promo.max_total_uses),
            max_uses_per_user=changes.get("max_uses_per_user", promo.max_uses_per_user),
        )
    if changes.get("sandbox_only") is False and settings.environment in ("prod", "production"):
        raise AppError("FORBIDDEN", "Promos cannot be moved out of sandbox in production.", 403)
    prev = {k: getattr(promo, k) for k in changes}
    for k, v in changes.items():
        setattr(promo, k, v)
    if "discount_value" in changes and promo.discount_type == "percentage":
        promo.discount_percent = promo.discount_value or 0
    admin_repo.record_audit(
        db, actor_id=admin.id, action="promo.update",
        target_type="promo", target_id=promo.id,
        previous_data=prev, new_data=changes, reason=body.reason, **_audit_ctx(request),
    )
    db.commit()
    return _promo_out(promo)


# --- PRD §17 credit ledger dashboard ---


@router.get("/credits", response_model=CreditDashboardOut)
def credit_dashboard(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("billing.view")),
) -> CreditDashboardOut:
    rows = admin_repo.credit_txns_today(db)
    dash = admin_service.credit_dashboard(rows)
    low = admin_repo.users_low_balance(db)
    return CreditDashboardOut(
        **dash,
        low_balance_users=[_user_row(db, u) for u in low],
    )


# =====================================================================
# Admin Panel Phase 5 — storage & compliance (PRD §18, §21).
#
# Storage actions gate on projects.manage; compliance triage on
# abuse.view/abuse.manage. Deletion-adjacent actions are refused by the
# service layer when a project is on legal hold, locked, or has an active
# job (§18.5). Raw storage keys are only echoed to privileged roles, and
# every admin action writes an audit row (§21.4/§21.6).
# =====================================================================


@router.get("/storage", response_model=StorageOverviewOut)
def storage_overview(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("projects.view")),
) -> StorageOverviewOut:
    rows = admin_repo.storage_bucket_bytes(db)
    ov = admin_service.storage_overview(rows)
    return StorageOverviewOut(
        total_bytes=ov["total_bytes"],
        buckets=ov["buckets"],
        estimated_cost_inr=ov["estimated_cost_inr"],
        key_counts=admin_repo.storage_key_counts(db),
    )


@router.get("/storage/retention", response_model=RetentionPage)
def retention_dashboard(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("projects.view")),
) -> RetentionPage:
    page, page_size, limit, offset = admin_service.paginate(page, page_size)
    rows = admin_repo.list_output_files_for_retention(db, limit=limit + offset)
    window = rows[offset:offset + limit]
    items = [
        RetentionItem(
            output_id=o.id, project_id=p.id, project_title=p.title,
            bucket=o.bucket, storage_key=o.storage_key, file_size=o.file_size,
            expires_at=o.expires_at, legal_hold=p.legal_hold,
            retention_extended=o.retention_extended, cleanup_failed=o.cleanup_failed,
            retention_state=admin_service.retention_bucket(
                o.expires_at, legal_hold=p.legal_hold,
                retention_extended=o.retention_extended, cleanup_failed=o.cleanup_failed,
            ),
        )
        for o, p in window
    ]
    return RetentionPage(items=items, total=len(rows), page=page, page_size=page_size)


@router.post("/projects/{project_id}/storage", response_model=StorageActionResponse)
def act_on_storage(
    project_id: str,
    body: StorageActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("projects.manage")),
) -> StorageActionResponse:
    project = _get_target_project(db, project_id)
    result = admin_service.apply_storage_action(
        db, admin=admin, project=project, action=body.action,
        reason=body.reason, hours=body.hours, audit_ctx=_audit_ctx(request),
    )
    db.commit()
    return StorageActionResponse(
        id=project.id, action=body.action,
        expires_at=project.expires_at, locked=project.locked, result=result,
    )


@router.get("/compliance", response_model=ComplianceOverviewOut)
def compliance_overview(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("abuse.view")),
) -> ComplianceOverviewOut:
    counts = admin_repo.compliance_overview_counts(db)
    return ComplianceOverviewOut(**admin_service.compliance_overview(counts))


@router.get("/compliance/reports", response_model=AbuseReportPage)
def list_compliance_reports(
    status: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("abuse.view")),
) -> AbuseReportPage:
    page, page_size, limit, offset = admin_service.paginate(page, page_size)
    rows, total = admin_repo.list_abuse_filtered(
        db, status=status, severity=severity, q=q, limit=limit, offset=offset,
    )
    return AbuseReportPage(
        items=[AbuseReportSummary.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
    )


def _get_target_report(db: Session, report_id: str):
    report = admin_repo.get_abuse(db, report_id)
    if report is None:
        raise AppError("NOT_FOUND", "Abuse report not found.", 404)
    return report


@router.get("/compliance/{report_id}", response_model=AbuseReportDetail)
def get_compliance_detail(
    report_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("abuse.view")),
) -> AbuseReportDetail:
    report = _get_target_report(db, report_id)
    project = admin_repo.get_project(db, report.project_id) if report.project_id else None
    owner_email = _user_email(db, project.user_id) if project else None
    reporter_email = _user_email(db, report.reported_by) if report.reported_by else None
    prev = admin_repo.project_previous_reports(db, report.project_id, exclude_id=report.id) if report.project_id else 0
    return AbuseReportDetail(
        id=report.id, project_id=report.project_id,
        project_title=project.title if project else None,
        project_owner_email=owner_email,
        reported_by=report.reported_by, reporter_email=reporter_email,
        reason=report.reason, status=report.status, severity=report.severity,
        assigned_reviewer=report.assigned_reviewer, resolution_note=report.resolution_note,
        legal_hold=project.legal_hold if project else False,
        legal_hold_reason=project.legal_hold_reason if project else None,
        processing_restricted=project.processing_restricted if project else False,
        downloads_disabled=project.downloads_disabled if project else False,
        previous_reports=prev,
        created_at=report.created_at, updated_at=report.updated_at,
    )


@router.patch("/compliance/{report_id}", response_model=AbuseReportSummary)
def set_report_severity(
    report_id: str,
    body: AbuseSeverityRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("abuse.manage")),
) -> AbuseReportSummary:
    report = _get_target_report(db, report_id)
    severity = admin_service.validate_abuse_severity(body.severity)
    admin_repo.update_abuse_fields(db, report, severity=severity, assigned_reviewer=admin.id)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="compliance.set_severity",
        target_type="abuse_report", target_id=report.id,
        details=admin_service.audit_details("compliance.set_severity", severity=severity),
        **_audit_ctx(request),
    )
    db.commit()
    return AbuseReportSummary.model_validate(report)


@router.post("/compliance/{report_id}/actions", response_model=ComplianceActionResponse)
def act_on_compliance(
    report_id: str,
    body: ComplianceActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("abuse.manage")),
) -> ComplianceActionResponse:
    report = _get_target_report(db, report_id)
    report, _project, target_user = admin_service.apply_compliance_action(
        db, admin=admin, report=report, action=body.action,
        reason=body.reason, audit_ctx=_audit_ctx(request),
    )
    db.commit()
    return ComplianceActionResponse(
        id=report.id, status=report.status,
        account_status=target_user.account_status.value if target_user else None,
    )


# =====================================================================
# Admin Panel Phase 6 — AI models, presets, feature flags, notifications,
# maintenance (PRD §19, §20, §23, §26.5, §26.6).
#
# Models/presets gate on models.manage / presets.manage; feature flags &
# maintenance on flags.manage / maintenance.manage; notifications on
# notifications.manage. Every mutation writes an audit row.
# =====================================================================


@router.get("/models", response_model=list[AIModelOut])
def list_models(
    model_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("models.view")),
) -> list[AIModelOut]:
    rows = admin_repo.list_models(db, model_type=model_type, status=status)
    return [AIModelOut.model_validate(m) for m in rows]


@router.post("/models", response_model=AIModelOut)
def register_model(
    body: AIModelCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("models.manage")),
) -> AIModelOut:
    model_type = admin_service.validate_model_type(body.model_type)
    if admin_repo.get_model_by_name_version(db, body.name, body.version) is not None:
        raise AppError("CONFLICT", "That model name + version is already registered.", 409)
    fields = body.model_dump()
    fields["model_type"] = model_type
    model = admin_repo.insert_model(db, **fields)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="model.register",
        target_type="ai_model", target_id=model.id,
        details=admin_service.audit_details("model.register", name=model.name, version=model.version),
        new_data={"name": model.name, "version": model.version, "model_type": model_type},
        **_audit_ctx(request),
    )
    db.commit()
    return AIModelOut.model_validate(model)


def _get_target_model(db: Session, model_id: str):
    model = admin_repo.get_model(db, model_id)
    if model is None:
        raise AppError("NOT_FOUND", "Model not found.", 404)
    return model


@router.patch("/models/{model_id}", response_model=AIModelOut)
def update_model(
    model_id: str,
    body: AIModelUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("models.manage")),
) -> AIModelOut:
    model = _get_target_model(db, model_id)
    changes = body.model_dump(exclude_unset=True)
    if "rollout_strategy" in changes or "rollout_percentage" in changes:
        strategy, pct = admin_service.validate_rollout(
            changes.get("rollout_strategy", model.rollout_strategy),
            changes.get("rollout_percentage", model.rollout_percentage),
        )
        changes["rollout_strategy"] = strategy
        changes["rollout_percentage"] = pct
    prev = {k: getattr(model, k) for k in changes}
    for k, v in changes.items():
        setattr(model, k, v)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="model.update",
        target_type="ai_model", target_id=model.id,
        previous_data=prev, new_data=changes, **_audit_ctx(request),
    )
    db.commit()
    return AIModelOut.model_validate(model)


@router.post("/models/{model_id}/actions", response_model=AIModelOut)
def act_on_model(
    model_id: str,
    body: ModelActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("models.manage")),
) -> AIModelOut:
    model = _get_target_model(db, model_id)
    model = admin_service.apply_model_action(
        db, admin=admin, model=model, action=body.action,
        reason=body.reason, audit_ctx=_audit_ctx(request),
    )
    db.commit()
    return AIModelOut.model_validate(model)


# --- PRD §20 processing presets ---


@router.get("/presets", response_model=list[PresetOut])
def list_presets(
    enabled: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("presets.view")),
) -> list[PresetOut]:
    return [PresetOut.model_validate(p) for p in admin_repo.list_presets(db, enabled=enabled)]


@router.post("/presets", response_model=PresetOut)
def create_preset(
    body: PresetWrite,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("presets.manage")),
) -> PresetOut:
    admin_service.validate_preset_fields(
        name=body.name, frame_sampling_rate=body.frame_sampling_rate,
        mask_expansion=body.mask_expansion, feathering=body.feathering,
        encoding_quality=body.encoding_quality, expected_credit_cost=body.expected_credit_cost,
    )
    fields = body.model_dump(exclude_unset=True)
    preset = admin_repo.insert_preset(db, **fields)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="preset.create",
        target_type="preset", target_id=preset.id,
        details=admin_service.audit_details("preset.create", name=preset.name),
        new_data=fields, **_audit_ctx(request),
    )
    db.commit()
    return PresetOut.model_validate(preset)


def _get_target_preset(db: Session, preset_id: str):
    preset = admin_repo.get_preset(db, preset_id)
    if preset is None:
        raise AppError("NOT_FOUND", "Preset not found.", 404)
    return preset


@router.patch("/presets/{preset_id}", response_model=PresetOut)
def update_preset(
    preset_id: str,
    body: PresetWrite,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("presets.manage")),
) -> PresetOut:
    preset = _get_target_preset(db, preset_id)
    changes = body.model_dump(exclude_unset=True)
    admin_service.validate_preset_fields(
        name=changes.get("name", preset.name),
        frame_sampling_rate=changes.get("frame_sampling_rate", preset.frame_sampling_rate),
        mask_expansion=changes.get("mask_expansion", preset.mask_expansion),
        feathering=changes.get("feathering", preset.feathering),
        encoding_quality=changes.get("encoding_quality", preset.encoding_quality),
        expected_credit_cost=changes.get("expected_credit_cost", preset.expected_credit_cost),
    )
    prev = {k: getattr(preset, k) for k in changes}
    for k, v in changes.items():
        setattr(preset, k, v)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="preset.update",
        target_type="preset", target_id=preset.id,
        previous_data=prev, new_data=changes, **_audit_ctx(request),
    )
    db.commit()
    return PresetOut.model_validate(preset)


@router.post("/presets/{preset_id}/set-default", response_model=PresetOut)
def set_default_preset(
    preset_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("presets.manage")),
) -> PresetOut:
    preset = _get_target_preset(db, preset_id)
    admin_repo.clear_default_preset(db)
    preset.is_default = True
    preset.enabled = True
    admin_repo.record_audit(
        db, actor_id=admin.id, action="preset.set_default",
        target_type="preset", target_id=preset.id,
        details=admin_service.audit_details("preset.set_default", name=preset.name),
        **_audit_ctx(request),
    )
    db.commit()
    return PresetOut.model_validate(preset)


# --- PRD §26.5 feature flags ---


@router.get("/feature-flags", response_model=list[FeatureFlagOut])
def list_feature_flags(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("config.view")),
) -> list[FeatureFlagOut]:
    rows = [
        {"key": f.key, "label": f.label, "enabled": f.enabled, "description": f.description}
        for f in admin_repo.list_feature_flags(db)
    ]
    return [FeatureFlagOut(**f) for f in admin_service.merge_feature_flags(rows)]


@router.patch("/feature-flags/{key}", response_model=FeatureFlagOut)
def update_feature_flag(
    key: str,
    body: FeatureFlagUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("flags.manage")),
) -> FeatureFlagOut:
    if key not in admin_service.FEATURE_FLAG_KEYS:
        raise AppError("NOT_FOUND", "Unknown feature flag.", 404)
    flag = admin_repo.upsert_feature_flag(
        db, key=key, enabled=body.enabled,
        label=admin_service._label_from_key(key),
    )
    admin_repo.record_audit(
        db, actor_id=admin.id, action="feature_flag.toggle",
        target_type="feature_flag", target_id=key,
        details=admin_service.audit_details("feature_flag.toggle", key=key, enabled=body.enabled),
        new_data={"enabled": body.enabled}, **_audit_ctx(request),
    )
    db.commit()
    return FeatureFlagOut(key=flag.key, label=flag.label, enabled=flag.enabled, description=flag.description)


# --- PRD §26.6 maintenance mode ---


@router.get("/maintenance", response_model=MaintenanceState)
def get_maintenance(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("config.view")),
) -> MaintenanceState:
    state = admin_repo.get_setting_json(db, admin_service.MAINTENANCE_SETTING_KEY)
    return MaintenanceState(**admin_service.normalise_maintenance(state))


@router.put("/maintenance", response_model=MaintenanceState)
def update_maintenance(
    body: MaintenanceState,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("maintenance.manage")),
) -> MaintenanceState:
    prev = admin_repo.get_setting_json(db, admin_service.MAINTENANCE_SETTING_KEY)
    payload = admin_service.normalise_maintenance(body.model_dump(mode="json"))
    admin_repo.set_setting_json(db, admin_service.MAINTENANCE_SETTING_KEY, payload)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="maintenance.update",
        target_type="system_setting", target_id=admin_service.MAINTENANCE_SETTING_KEY,
        previous_data=prev, new_data=payload, **_audit_ctx(request),
    )
    db.commit()
    # Bust the enforcement middleware's TTL cache so the toggle applies now.
    from app.core.maintenance import invalidate_cache
    invalidate_cache()
    return MaintenanceState(**payload)


# --- PRD §23 notification templates + broadcasts ---


@router.get("/notifications/templates", response_model=list[NotificationTemplateOut])
def list_notification_templates(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("notifications.view")),
) -> list[NotificationTemplateOut]:
    return [NotificationTemplateOut.model_validate(t) for t in admin_repo.list_templates(db)]


def _get_target_template(db: Session, template_id: str):
    tmpl = admin_repo.get_template(db, template_id)
    if tmpl is None:
        raise AppError("NOT_FOUND", "Template not found.", 404)
    return tmpl


@router.patch("/notifications/templates/{template_id}", response_model=NotificationTemplateOut)
def update_notification_template(
    template_id: str,
    body: NotificationTemplateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("notifications.manage")),
) -> NotificationTemplateOut:
    tmpl = _get_target_template(db, template_id)
    changes = body.model_dump(exclude_unset=True)
    prev = {k: getattr(tmpl, k) for k in changes}
    tmpl = admin_repo.upsert_template(db, key=tmpl.key, **changes)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="notification_template.update",
        target_type="notification_template", target_id=tmpl.id,
        previous_data=prev, new_data=changes, **_audit_ctx(request),
    )
    db.commit()
    return NotificationTemplateOut.model_validate(tmpl)


@router.post(
    "/notifications/templates/{template_id}/preview",
    response_model=TemplatePreviewResponse,
)
def preview_notification_template(
    template_id: str,
    body: TemplatePreviewRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("notifications.view")),
) -> TemplatePreviewResponse:
    tmpl = _get_target_template(db, template_id)
    rendered = admin_service.render_template_preview(
        {"subject": tmpl.subject, "html_content": tmpl.html_content, "text_content": tmpl.text_content},
        body.variables,
    )
    return TemplatePreviewResponse(**rendered)


@router.post("/notifications/broadcast", response_model=BroadcastResponse)
def send_broadcast(
    body: BroadcastRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("notifications.manage")),
) -> BroadcastResponse:
    broadcast = admin_service.send_broadcast(
        db, admin=admin, kind=body.kind, title=body.title, message=body.message,
        target=body.target, target_plan=body.target_plan, audit_ctx=_audit_ctx(request),
    )
    db.commit()
    return BroadcastResponse(
        id=broadcast.id, kind=broadcast.kind,
        target=broadcast.target, recipient_count=broadcast.recipient_count,
    )


# =====================================================================
# PRD Phase 7 — Analytics, Exports, System Health, Admin Mgmt, Search, Secrets
# =====================================================================


# --- §24 Analytics & reports ---


@router.get("/analytics", response_model=AnalyticsOut)
def get_analytics(
    window_days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("analytics.view")),
) -> AnalyticsOut:
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    counts = admin_repo.analytics_counts(db, since=since)
    business = admin_repo.business_analytics_counts(db)
    return AnalyticsOut(
        product=admin_service.product_analytics(counts),
        processing=admin_service.processing_analytics(counts),
        business=business,
        cost=admin_service.cost_analytics(counts),
        window_days=window_days,
    )


@router.post("/exports")
def create_export(
    body: ExportRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("analytics.export")),
) -> Response:
    fmt = admin_service.validate_export_format(body.format)
    columns = admin_repo.EXPORT_COLUMNS.get(body.dataset, ())
    rows = admin_repo.export_rows(db, body.dataset)
    rows = admin_service.filter_export_rows(rows, columns)

    # §27 — record that admin data left the system (who/what/how many).
    admin_repo.record_audit(
        db, actor_id=admin.id, action="data.export",
        target_type="export", target_id=body.dataset,
        details=admin_service.audit_details(
            "data.export", dataset=body.dataset, format=fmt, row_count=len(rows),
        ),
        **_audit_ctx(request),
    )
    db.commit()

    if fmt == "json":
        import json

        payload = json.dumps({"dataset": body.dataset, "rows": rows}, default=str)
        media = "application/json"
        ext = "json"
    else:
        payload = admin_service.to_csv(rows, columns)
        media = "text/csv"
        ext = "csv"
    filename = f"{body.dataset}-export.{ext}"
    return Response(
        content=payload, media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- §25 System health ---


@router.get("/system-health", response_model=SystemHealthOut)
def get_system_health(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("health.view")),
) -> SystemHealthOut:
    from app.services import health_monitor

    checks, probe = health_monitor.collect(db, admin_repo.health_probe_counts(db))
    services = admin_service.service_status_list({
        name: row.get("ok") for name, row in checks.items()
    })
    for service in services:
        detail = checks.get(service["name"], {})
        service["detail"] = detail.get("detail")
        service["latency_ms"] = detail.get("latency_ms")
    metrics = admin_service.evaluate_health_metrics(probe)
    overall = admin_service.overall_health(services, metrics)
    return SystemHealthOut(
        overall=overall,
        services=services,
        metrics=metrics,
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("health.view")),
) -> list[IncidentOut]:
    return [IncidentOut.model_validate(i) for i in admin_repo.list_incidents(db, status=status)]


@router.post("/incidents", response_model=IncidentOut)
def create_incident(
    body: IncidentCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("health.manage")),
) -> IncidentOut:
    inc = admin_repo.insert_incident(
        db, service=body.service, severity=body.severity,
        title=body.title, detail=body.detail, status="open",
    )
    admin_repo.record_audit(
        db, actor_id=admin.id, action="incident.open",
        target_type="incident", target_id=inc.id,
        details=admin_service.audit_details("incident.open", service=body.service, severity=body.severity),
        new_data={"title": body.title, "severity": body.severity}, **_audit_ctx(request),
    )
    db.commit()
    return IncidentOut.model_validate(inc)


@router.post("/incidents/{incident_id}/actions", response_model=IncidentOut)
def act_on_incident(
    incident_id: str,
    body: IncidentActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("health.manage")),
) -> IncidentOut:
    inc = admin_repo.get_incident(db, incident_id)
    if inc is None:
        raise AppError("NOT_FOUND", "Incident not found.", 404)
    effects = admin_service.incident_action_effects(body.action)
    note = (body.note or "").strip()
    if effects["requires_note"] and not note:
        raise AppError("VALIDATION_ERROR", "This action requires a note.", 422)

    prev = {"status": inc.status, "silenced_until": inc.silenced_until}
    if effects["status"] is not None:
        inc.status = effects["status"]
        if effects["status"] == "resolved":
            inc.resolved_at = datetime.now(timezone.utc)
        elif effects["status"] == "open":
            inc.resolved_at = None
    if body.action == "acknowledge":
        inc.acknowledged_by = admin.id
    if effects["silence"]:
        minutes = body.minutes or 60
        inc.silenced_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    if note:
        history = list(inc.notes or [])
        history.append({"by": admin.id, "note": note})
        inc.notes = history
    inc.updated_at = datetime.now(timezone.utc)
    db.flush()

    admin_repo.record_audit(
        db, actor_id=admin.id, action=f"incident.{body.action}",
        target_type="incident", target_id=inc.id,
        previous_data=prev, new_data={"status": inc.status}, reason=note or None,
        **_audit_ctx(request),
    )
    db.commit()
    return IncidentOut.model_validate(inc)


# --- §28 Administrator management (super-admin only) ---


def _admin_list_item(u: User) -> AdminListItem:
    role = effective_admin_role(u.role.value, u.admin_role)
    return AdminListItem(
        id=u.id, email=u.email, full_name=u.full_name, admin_role=role,
        account_status=u.account_status.value, mfa_enabled=bool(getattr(u, "mfa_enabled", False)),
        last_login_at=getattr(u, "last_login_at", None), created_at=u.created_at,
        admin_created_by=getattr(u, "admin_created_by", None),
    )


@router.get("/administrators", response_model=list[AdminListItem])
def list_administrators(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("admins.view")),
) -> list[AdminListItem]:
    return [_admin_list_item(u) for u in admin_repo.list_admins(db)]


@router.post("/administrators", response_model=AdminListItem)
def invite_administrator(
    body: AdminInviteRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("admins.manage")),
) -> AdminListItem:
    from app.core.security import hash_password
    import secrets as _secrets

    if body.admin_role not in _known_admin_roles():
        raise AppError("VALIDATION_ERROR", f"Unknown admin role '{body.admin_role}'.", 422)
    existing = db.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if existing is not None:
        raise AppError("CONFLICT", "A user with that email already exists.", 409)

    # Invited admins get a random unusable password; they set one via the reset
    # flow. MFA is required for staff (§28.1).
    temp = _secrets.token_urlsafe(24)
    user = User(
        email=body.email, full_name=body.full_name, password_hash=hash_password(temp),
        role=UserRole.admin, admin_role=body.admin_role, email_verified=False,
        account_status=AccountStatus.active,
    )
    if hasattr(User, "mfa_required"):
        user.mfa_required = True
    if hasattr(User, "admin_created_by"):
        user.admin_created_by = admin.id
    if hasattr(User, "admin_invited_at"):
        user.admin_invited_at = datetime.now(timezone.utc)
    db.add(user)
    db.flush()

    admin_repo.record_audit(
        db, actor_id=admin.id, action="admin.invite",
        target_type="user", target_id=user.id,
        details=admin_service.audit_details("admin.invite", email=body.email, admin_role=body.admin_role),
        new_data={"admin_role": body.admin_role}, **_audit_ctx(request),
    )
    db.commit()
    return _admin_list_item(user)


@router.post("/administrators/{admin_id}/actions", response_model=AdminListItem)
def act_on_administrator(
    admin_id: str,
    body: AdminMgmtActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("admins.manage")),
) -> AdminListItem:
    target = admin_repo.get_user(db, admin_id)
    if target is None:
        raise AppError("NOT_FOUND", "Administrator not found.", 404)
    target_role = effective_admin_role(target.role.value, target.admin_role)

    # Pure guard rails (self-target, role validity, reason on destructive).
    admin_service.validate_admin_mgmt_action(
        body.action, actor_id=admin.id, target_id=target.id,
        target_admin_role=target_role, new_role=body.new_role, reason=body.reason,
    )

    # Last-super-admin protection (needs a live count): block demoting/suspending
    # /removing the final active super_admin.
    demotes_super = (
        target_role == "super_admin"
        and (
            body.action in ("suspend", "remove")
            or (body.action in ("assign_role", "change_role") and body.new_role != "super_admin")
        )
    )
    if demotes_super and admin_repo.count_active_super_admins(db, exclude_id=target.id) == 0:
        raise AppError("VALIDATION_ERROR", "Cannot remove the last active super administrator.", 422)

    prev = {"admin_role": target.admin_role, "account_status": target.account_status.value}
    action = body.action
    if action in ("assign_role", "change_role"):
        target.admin_role = body.new_role
        target.role = UserRole.admin
    elif action == "suspend":
        target.account_status = AccountStatus.suspended
    elif action == "reactivate":
        target.account_status = AccountStatus.active
    elif action == "revoke_sessions":
        admin_repo.revoke_all_sessions(db, target.id)
    elif action == "require_password_reset":
        if hasattr(target, "must_reset_password"):
            target.must_reset_password = True
    elif action == "require_mfa":
        if hasattr(target, "mfa_required"):
            target.mfa_required = True
    elif action == "remove":
        # Demote out of staff rather than hard-delete: preserves audit linkage.
        target.admin_role = None
        target.role = UserRole.user
    db.flush()

    admin_repo.record_audit(
        db, actor_id=admin.id, action=f"admin.{action}",
        target_type="user", target_id=target.id,
        previous_data=prev,
        new_data={"admin_role": target.admin_role, "account_status": target.account_status.value},
        reason=body.reason, **_audit_ctx(request),
    )
    db.commit()
    return _admin_list_item(target)


def _known_admin_roles() -> set:
    """Known admin-role names (for invite validation) — from the RBAC map."""
    from app.services.admin_permissions import PERMISSIONS

    return set(PERMISSIONS.keys())


# --- §29 Global search ---


@router.get("/search", response_model=GlobalSearchOut)
def global_search(
    q: str = Query(..., min_length=1, max_length=255),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> GlobalSearchOut:
    token = q.strip()
    entity_types = admin_service.classify_search_query(token)
    grouped = admin_repo.search_entities(db, entity_types=entity_types, token=token)
    groups = [
        {"entity_type": etype, "items": grouped[etype]}
        for etype in entity_types
        if etype in grouped
    ]
    return GlobalSearchOut(query=token, groups=groups)


# --- §26.7 Secret descriptors (never full private values) ---

# Map descriptor names → the settings attribute holding the raw value.
_SECRET_SOURCES = {
    "jwt_secret": "secret_key",
    "razorpay_key_id": "razorpay_key_id",
    "razorpay_key_secret": "razorpay_key_secret",
    "razorpay_webhook_secret": "razorpay_webhook_secret",
    "storage_access_key": "minio_access_key",
    "storage_secret_key": "minio_secret_key",
    "database_url": "database_url",
    "email_password": "smtp_password",
}


@router.get("/secrets", response_model=SecretsOut)
def list_secrets(
    _admin: User = Depends(require_permission("secrets.view")),
) -> SecretsOut:
    descriptors = []
    for name in admin_service.SECRET_KEYS:
        attr = _SECRET_SOURCES.get(name, name)
        raw = getattr(settings, attr, "") or ""
        descriptors.append(admin_service.describe_secret(name, raw))
    return SecretsOut(secrets=descriptors)


__all__ = ["router"]
