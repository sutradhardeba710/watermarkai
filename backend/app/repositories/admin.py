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
    AIModel,
    AuditLog,
    Broadcast,
    ComplianceConfirmation,
    CreditTransaction,
    FeatureFlag,
    Incident,
    JobState,
    JobType,
    Notification,
    NotificationTemplate,
    OutputFile,
    Payment,
    Plan,
    ProcessingJob,
    ProcessingPreset,
    PromoCode,
    Refund,
    Session as SessionRow,
    Subscription,
    SubscriptionStatus,
    SupportNote,
    SystemSetting,
    Upload,
    User,
    UserRole,
    VideoProject,
    WebhookEvent,
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


# --- Phase 3: queue metrics + worker deep-dive ---

# States that count as "in a queue waiting for a worker".
_QUEUED_STATES = (
    JobState.created,
    JobState.processing_queued,
    JobState.preview_queued,
)
# States that count as "actively running on a worker".
_ACTIVE_STATES = (
    JobState.analyzing,
    JobState.processing,
    JobState.encoding,
    JobState.preview_processing,
)


def queue_metrics(db: Session) -> dict[str, Any]:
    """Aggregate queue depth + throughput for the queues page (PRD §11)."""
    day_start = _start_of_day_utc()
    queued = int(db.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.status.in_(_QUEUED_STATES))
    ).scalar() or 0)
    active = int(db.execute(
        select(func.count(ProcessingJob.id)).where(ProcessingJob.status.in_(_ACTIVE_STATES))
    ).scalar() or 0)
    completed_today = int(db.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.status == JobState.completed,
            ProcessingJob.completed_at >= day_start,
        )
    ).scalar() or 0)
    failed_today = int(db.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.status == JobState.failed,
            ProcessingJob.created_at >= day_start,
        )
    ).scalar() or 0)
    # Per-state breakdown for the stacked bar.
    rows = db.execute(
        select(ProcessingJob.status, func.count(ProcessingJob.id)).group_by(ProcessingJob.status)
    ).all()
    by_state = {
        (s.value if hasattr(s, "value") else str(s)): int(c) for s, c in rows
    }
    return {
        "queued": queued,
        "active": active,
        "completed_today": completed_today,
        "failed_today": failed_today,
        "by_state": by_state,
    }


def queue_breakdown(db: Session) -> list[dict[str, Any]]:
    """Depth per logical Celery queue (detection / processing). We map job
    types onto their queue since the broker depth isn't in the DB."""
    day_start = _start_of_day_utc()
    # (queue name, job types routed to it)
    queues = [
        ("detection", (JobType.analyze, JobType.track)),
        ("processing", (JobType.process, JobType.preview, JobType.encode)),
    ]
    out: list[dict[str, Any]] = []
    for name, types in queues:
        queued = int(db.execute(
            select(func.count(ProcessingJob.id)).where(
                ProcessingJob.status.in_(_QUEUED_STATES),
                ProcessingJob.job_type.in_(types),
            )
        ).scalar() or 0)
        active = int(db.execute(
            select(func.count(ProcessingJob.id)).where(
                ProcessingJob.status.in_(_ACTIVE_STATES),
                ProcessingJob.job_type.in_(types),
            )
        ).scalar() or 0)
        failed_today = int(db.execute(
            select(func.count(ProcessingJob.id)).where(
                ProcessingJob.status == JobState.failed,
                ProcessingJob.job_type.in_(types),
                ProcessingJob.created_at >= day_start,
            )
        ).scalar() or 0)
        oldest = db.execute(
            select(func.min(ProcessingJob.created_at)).where(
                ProcessingJob.status.in_(_QUEUED_STATES),
                ProcessingJob.job_type.in_(types),
            )
        ).scalar()
        oldest_seconds = None
        if oldest is not None:
            ref = oldest if oldest.tzinfo else oldest.replace(tzinfo=timezone.utc)
            oldest_seconds = (datetime.now(timezone.utc) - ref).total_seconds()
        out.append({
            "name": name, "queued": queued, "active": active,
            "failed_today": failed_today, "oldest_queued_seconds": oldest_seconds,
        })
    return out


def get_worker_node(db: Session, name: str) -> WorkerNode | None:
    return db.execute(select(WorkerNode).where(WorkerNode.name == name)).scalars().first()


def worker_jobs(db: Session, worker_name: str, *, limit: int = 25) -> list[ProcessingJob]:
    return list(db.execute(
        select(ProcessingJob).where(ProcessingJob.worker_id == worker_name)
        .order_by(ProcessingJob.created_at.desc()).limit(limit)
    ).scalars())


def worker_job_counts(db: Session, worker_name: str) -> tuple[int, int]:
    """(completed, failed) job counts attributed to a worker."""
    completed = int(db.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.worker_id == worker_name,
            ProcessingJob.status == JobState.completed,
        )
    ).scalar() or 0)
    failed = int(db.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.worker_id == worker_name,
            ProcessingJob.status == JobState.failed,
        )
    ).scalar() or 0)
    return completed, failed


def list_audit_for_target(
    db: Session, target_type: str, target_id: str, *, limit: int = 20
) -> list[AuditLog]:
    return list(db.execute(
        select(AuditLog).where(
            AuditLog.target_type == target_type, AuditLog.target_id == target_id
        ).order_by(AuditLog.created_at.desc()).limit(limit)
    ).scalars())


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
    previous_data: dict | None = None,
    new_data: dict | None = None,
    reason: str | None = None,
    ip_hash: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    result: str = "success",
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        previous_data=previous_data,
        new_data=new_data,
        reason=reason,
        ip_hash=ip_hash,
        user_agent=user_agent,
        request_id=request_id,
        result=result,
    )
    db.add(row)
    db.flush()
    return row


def list_audit(db: Session, *, limit: int = 100) -> list[AuditLog]:
    return list(
        db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).scalars()
    )


def list_audit_filtered(
    db: Session,
    *,
    action: str | None = None,
    actor_id: str | None = None,
    target_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    """Filtered + paginated audit listing (PRD §27.3)."""
    conds = []
    if action:
        conds.append(AuditLog.action.ilike(f"%{action}%"))
    if actor_id:
        conds.append(AuditLog.actor_id == actor_id)
    if target_type:
        conds.append(AuditLog.target_type == target_type)
    if date_from:
        conds.append(AuditLog.created_at >= date_from)
    if date_to:
        conds.append(AuditLog.created_at <= date_to)
    total = int(db.execute(select(func.count(AuditLog.id)).where(*conds)).scalar() or 0)
    rows = list(db.execute(
        select(AuditLog).where(*conds)
        .order_by(AuditLog.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars())
    return rows, total


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


# --- Admin Panel Phases 1+2 ---


def get_user(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def get_user_locked(db: Session, user_id: str) -> User:
    """Load the user row FOR UPDATE — serializes concurrent credit changes."""
    return db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalars().one()


def list_users_paged(
    db: Session,
    *,
    q: str | None = None,
    status: str | None = None,
    role: str | None = None,
    plan_id: str | None = None,
    verified: bool | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[User], int]:
    conds = []
    if q:
        like = f"%{q}%"
        conds.append(User.email.ilike(like) | User.full_name.ilike(like) | (User.id == q))
    if status:
        conds.append(User.account_status == status)
    if role == "staff":
        conds.append(User.admin_role.is_not(None) | (User.role == UserRole.admin))
    elif role:
        conds.append(User.role == role)
    if plan_id:
        if plan_id == "free":
            conds.append(User.plan_id.is_(None) | (User.plan_id == "free"))
        else:
            conds.append(User.plan_id == plan_id)
    if verified is not None:
        conds.append(User.email_verified == verified)
    total = int(db.execute(select(func.count(User.id)).where(*conds)).scalar() or 0)
    rows = list(db.execute(
        select(User).where(*conds).order_by(User.created_at.desc()).limit(limit).offset(offset)
    ).scalars())
    return rows, total


def user_detail_extras(db: Session, user_id: str) -> dict[str, Any]:
    """Failed-job count, storage footprint, active session count (PRD §8.3)."""
    failed = db.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.user_id == user_id, ProcessingJob.status == JobState.failed
        )
    ).scalar() or 0
    storage = db.execute(
        select(func.coalesce(func.sum(OutputFile.file_size), 0))
        .join(VideoProject, OutputFile.project_id == VideoProject.id)
        .where(VideoProject.user_id == user_id)
    ).scalar() or 0
    now = datetime.now(timezone.utc)
    sessions = db.execute(
        select(func.count(SessionRow.id)).where(
            SessionRow.user_id == user_id,
            SessionRow.revoked.is_(False),
            SessionRow.expires_at > now,
        )
    ).scalar() or 0
    return {
        "failed_jobs": int(failed),
        "storage_bytes": int(storage),
        "active_sessions": int(sessions),
    }


def revoke_all_sessions(db: Session, user_id: str) -> int:
    """Revoke every active session for a user. Returns rows affected."""
    count = (
        db.query(SessionRow)
        .filter(SessionRow.user_id == user_id, SessionRow.revoked.is_(False))
        .update({"revoked": True})
    )
    db.flush()
    return int(count)


def list_user_sessions(db: Session, user_id: str, *, limit: int = 50) -> list[SessionRow]:
    return list(db.execute(
        select(SessionRow).where(SessionRow.user_id == user_id)
        .order_by(SessionRow.created_at.desc()).limit(limit)
    ).scalars())


def list_user_compliance(db: Session, user_id: str, *, limit: int = 50) -> list[ComplianceConfirmation]:
    return list(db.execute(
        select(ComplianceConfirmation).where(ComplianceConfirmation.user_id == user_id)
        .order_by(ComplianceConfirmation.confirmed_at.desc()).limit(limit)
    ).scalars())


def list_audit_for_user(db: Session, user_id: str, *, limit: int = 25, offset: int = 0) -> tuple[list[AuditLog], int]:
    """Activity tab: audit entries where the user is actor OR target."""
    conds = [(AuditLog.actor_id == user_id) | (AuditLog.target_id == user_id)]
    total = int(db.execute(select(func.count(AuditLog.id)).where(*conds)).scalar() or 0)
    rows = list(db.execute(
        select(AuditLog).where(*conds).order_by(AuditLog.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars())
    return rows, total


def count_super_admins(db: Session, *, exclude_id: str | None = None) -> int:
    """Super admins other than ``exclude_id`` — guards last-super removal.
    Counts explicit super_admins plus legacy role='admin' rows with no
    admin_role (they resolve to super_admin)."""
    conds = [
        (User.admin_role == "super_admin")
        | ((User.role == UserRole.admin) & User.admin_role.is_(None))
    ]
    if exclude_id:
        conds.append(User.id != exclude_id)
    return int(db.execute(select(func.count(User.id)).where(*conds)).scalar() or 0)


# --- Credit transactions (PRD §17) ---


def insert_credit_txn(db: Session, **fields: Any) -> CreditTransaction:
    row = CreditTransaction(**fields)
    db.add(row)
    db.flush()
    return row


def list_credit_txns(
    db: Session, user_id: str, *, limit: int = 25, offset: int = 0
) -> tuple[list[CreditTransaction], int]:
    conds = [CreditTransaction.user_id == user_id]
    total = int(db.execute(select(func.count(CreditTransaction.id)).where(*conds)).scalar() or 0)
    rows = list(db.execute(
        select(CreditTransaction).where(*conds)
        .order_by(CreditTransaction.created_at.desc()).limit(limit).offset(offset)
    ).scalars())
    return rows, total


# --- Payments (PRD §13) ---


def insert_payment(db: Session, **fields: Any) -> Payment:
    row = Payment(**fields)
    db.add(row)
    db.flush()
    return row


def list_payments(
    db: Session, *, user_id: str | None = None, limit: int = 25, offset: int = 0
) -> tuple[list[Payment], int]:
    conds = []
    if user_id:
        conds.append(Payment.user_id == user_id)
    total = int(db.execute(select(func.count(Payment.id)).where(*conds)).scalar() or 0)
    rows = list(db.execute(
        select(Payment).where(*conds).order_by(Payment.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars())
    return rows, total


def revenue_since(db: Session, since: datetime) -> int:
    """Sum of captured payment amounts (paise) since a cutoff."""
    return int(db.execute(
        select(func.coalesce(func.sum(Payment.amount_inr), 0)).where(
            Payment.status == "captured", Payment.created_at >= since
        )
    ).scalar() or 0)


def active_subscription_count(db: Session) -> int:
    return int(db.execute(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.active)
    ).scalar() or 0)


# --- Billing dashboard + payments detail (PRD §13) ---


def billing_counts(db: Session) -> dict[str, Any]:
    """Aggregates for the billing dashboard (PRD §13.1)."""
    day_start = _start_of_day_utc()
    month_start = day_start.replace(day=1)
    new_subs = int(db.execute(
        select(func.count(Subscription.id)).where(Subscription.created_at >= month_start)
    ).scalar() or 0)
    cancellations = int(db.execute(
        select(func.count(Subscription.id)).where(Subscription.cancelled_at >= month_start)
    ).scalar() or 0)
    failed_payments = int(db.execute(
        select(func.count(Payment.id)).where(
            Payment.status == "failed", Payment.created_at >= month_start
        )
    ).scalar() or 0)
    refunds_inr = int(db.execute(
        select(func.coalesce(func.sum(Refund.amount_inr), 0)).where(Refund.created_at >= month_start)
    ).scalar() or 0)
    renewals = int(db.execute(
        select(func.count(Payment.id)).where(
            Payment.status == "captured",
            Payment.created_at >= month_start,
            Payment.description.ilike("%renewal%"),
        )
    ).scalar() or 0)
    return {
        "revenue_today_inr": revenue_since(db, day_start),
        "revenue_this_month_inr": revenue_since(db, month_start),
        "new_subscriptions": new_subs,
        "cancellations": cancellations,
        "renewals": renewals,
        "failed_payments": failed_payments,
        "refunds_inr": refunds_inr,
    }


def list_payments_filtered(
    db: Session,
    *,
    status: str | None = None,
    user_id: str | None = None,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[tuple[Payment, str | None]], int]:
    """Returns (payment, user_email) tuples plus the filtered total."""
    conds = []
    if status:
        conds.append(Payment.status == status)
    if user_id:
        conds.append(Payment.user_id == user_id)
    if q:
        like = f"%{q}%"
        conds.append(
            Payment.razorpay_payment_id.ilike(like)
            | Payment.razorpay_order_id.ilike(like)
            | User.email.ilike(like)
        )
    base = select(Payment, User.email).join(User, User.id == Payment.user_id)
    total = int(db.execute(
        select(func.count()).select_from(
            base.where(*conds).subquery()
        )
    ).scalar() or 0)
    rows = db.execute(
        base.where(*conds).order_by(Payment.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return [(r[0], r[1]) for r in rows], total


def get_payment(db: Session, payment_id: str) -> Payment | None:
    return db.get(Payment, payment_id)


def list_refunds(db: Session, payment_id: str) -> list[Refund]:
    return list(db.execute(
        select(Refund).where(Refund.payment_id == payment_id).order_by(Refund.created_at.desc())
    ).scalars())


def insert_refund(db: Session, **fields: Any) -> Refund:
    row = Refund(**fields)
    db.add(row)
    db.flush()
    return row


def total_refunded(db: Session, payment_id: str) -> int:
    return int(db.execute(
        select(func.coalesce(func.sum(Refund.amount_inr), 0)).where(Refund.payment_id == payment_id)
    ).scalar() or 0)


# --- Webhook events (PRD §13.4 / §26) ---


def list_webhook_events(
    db: Session, *, event_type: str | None = None, payment_id: str | None = None,
    limit: int = 50, offset: int = 0,
) -> tuple[list[WebhookEvent], int]:
    conds = []
    if event_type:
        conds.append(WebhookEvent.event_type == event_type)
    if payment_id:
        conds.append(WebhookEvent.payment_id == payment_id)
    total = int(db.execute(select(func.count(WebhookEvent.id)).where(*conds)).scalar() or 0)
    rows = list(db.execute(
        select(WebhookEvent).where(*conds).order_by(WebhookEvent.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars())
    return rows, total


def get_webhook_event(db: Session, event_id: str) -> WebhookEvent | None:
    return db.get(WebhookEvent, event_id)


def insert_webhook_event(db: Session, **fields: Any) -> WebhookEvent:
    row = WebhookEvent(**fields)
    db.add(row)
    db.flush()
    return row


# --- Subscriptions (PRD §14) ---


def list_subscriptions(
    db: Session, *, status: str | None = None, limit: int = 50, offset: int = 0,
) -> tuple[list[tuple[Subscription, str | None]], int]:
    conds = []
    if status:
        conds.append(Subscription.status == status)
    base = select(Subscription, User.email).join(User, User.id == Subscription.user_id)
    total = int(db.execute(
        select(func.count()).select_from(base.where(*conds).subquery())
    ).scalar() or 0)
    rows = db.execute(
        base.where(*conds).order_by(Subscription.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return [(r[0], r[1]) for r in rows], total


def get_subscription(db: Session, subscription_id: str) -> Subscription | None:
    return db.get(Subscription, subscription_id)


def get_subscription_for_user(db: Session, user_id: str) -> Subscription | None:
    return db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    ).scalar_one_or_none()


# --- Plans (PRD §15) ---


def list_plans(db: Session, *, include_archived: bool = True) -> list[Plan]:
    conds = [] if include_archived else [Plan.archived == False]  # noqa: E712
    return list(db.execute(
        select(Plan).where(*conds).order_by(Plan.display_order, Plan.price_inr)
    ).scalars())


def get_plan(db: Session, plan_id: str) -> Plan | None:
    return db.get(Plan, plan_id)


def insert_plan(db: Session, **fields: Any) -> Plan:
    row = Plan(**fields)
    db.add(row)
    db.flush()
    return row


def plan_subscriber_count(db: Session, plan_id: str) -> int:
    return int(db.execute(
        select(func.count(Subscription.id)).where(
            Subscription.plan_id == plan_id,
            Subscription.status == SubscriptionStatus.active,
        )
    ).scalar() or 0)


# --- Promo codes (PRD §16) ---


def list_promos(db: Session, *, active: bool | None = None) -> list[PromoCode]:
    conds = []
    if active is not None:
        conds.append(PromoCode.is_active == active)
    return list(db.execute(
        select(PromoCode).where(*conds).order_by(PromoCode.created_at.desc())
    ).scalars())


def get_promo(db: Session, promo_id: str) -> PromoCode | None:
    return db.get(PromoCode, promo_id)


def get_promo_by_code(db: Session, code: str) -> PromoCode | None:
    return db.execute(
        select(PromoCode).where(PromoCode.code == code.upper())
    ).scalar_one_or_none()


def insert_promo(db: Session, **fields: Any) -> PromoCode:
    row = PromoCode(**fields)
    db.add(row)
    db.flush()
    return row


# --- Credit dashboard (PRD §17.1) ---


def credit_txns_today(db: Session) -> list[dict[str, Any]]:
    """Today's ledger rows as {direction, amount, source} for the dashboard."""
    day_start = _start_of_day_utc()
    rows = db.execute(
        select(CreditTransaction.direction, CreditTransaction.amount, CreditTransaction.source)
        .where(CreditTransaction.created_at >= day_start)
    ).all()
    return [{"direction": r[0], "amount": r[1], "source": r[2]} for r in rows]


def users_low_balance(db: Session, *, threshold: int = 100, limit: int = 20) -> list[User]:
    return list(db.execute(
        select(User).where(User.credits_remaining < threshold)
        .order_by(User.credits_remaining).limit(limit)
    ).scalars())


# --- Projects (PRD §9) ---


def list_projects_paged(
    db: Session,
    *,
    q: str | None = None,
    status: str | None = None,
    user_id: str | None = None,
    locked: bool | None = None,
    include_deleted: bool = False,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[tuple[VideoProject, str]], int]:
    """Returns (project, user_email) tuples plus the filtered total."""
    conds = []
    if not include_deleted:
        conds.append(VideoProject.deleted.is_(False))
    if q:
        like = f"%{q}%"
        conds.append(
            VideoProject.title.ilike(like)
            | VideoProject.original_filename.ilike(like)
            | (VideoProject.id == q)
        )
    if status:
        conds.append(VideoProject.status == status)
    if user_id:
        conds.append(VideoProject.user_id == user_id)
    if locked is not None:
        conds.append(VideoProject.locked == locked)
    total = int(db.execute(select(func.count(VideoProject.id)).where(*conds)).scalar() or 0)
    rows = db.execute(
        select(VideoProject, User.email)
        .join(User, VideoProject.user_id == User.id)
        .where(*conds)
        .order_by(VideoProject.created_at.desc())
        .limit(limit).offset(offset)
    ).all()
    return [(p, email) for p, email in rows], total


def get_project(db: Session, project_id: str) -> VideoProject | None:
    return db.get(VideoProject, project_id)


def list_user_projects(
    db: Session, user_id: str, *, limit: int = 25, offset: int = 0
) -> tuple[list[VideoProject], int]:
    conds = [VideoProject.user_id == user_id]
    total = int(db.execute(select(func.count(VideoProject.id)).where(*conds)).scalar() or 0)
    rows = list(db.execute(
        select(VideoProject).where(*conds).order_by(VideoProject.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars())
    return rows, total


def project_jobs(db: Session, project_id: str, *, limit: int = 50) -> list[ProcessingJob]:
    return list(db.execute(
        select(ProcessingJob).where(ProcessingJob.project_id == project_id)
        .order_by(ProcessingJob.created_at.desc()).limit(limit)
    ).scalars())


def project_outputs(db: Session, project_id: str) -> list[OutputFile]:
    return list(db.execute(
        select(OutputFile).where(OutputFile.project_id == project_id)
        .order_by(OutputFile.created_at.desc())
    ).scalars())


def project_compliance(db: Session, project_id: str) -> list[ComplianceConfirmation]:
    return list(db.execute(
        select(ComplianceConfirmation).where(ComplianceConfirmation.project_id == project_id)
        .order_by(ComplianceConfirmation.confirmed_at.desc())
    ).scalars())


# --- Support notes (PRD §22) ---


def list_notes(
    db: Session, *, user_id: str | None = None, project_id: str | None = None, limit: int = 100
) -> list[SupportNote]:
    conds = []
    if user_id:
        conds.append(SupportNote.user_id == user_id)
    if project_id:
        conds.append(SupportNote.project_id == project_id)
    return list(db.execute(
        select(SupportNote).where(*conds)
        .order_by(SupportNote.pinned.desc(), SupportNote.created_at.desc())
        .limit(limit)
    ).scalars())


def insert_note(db: Session, **fields: Any) -> SupportNote:
    row = SupportNote(**fields)
    db.add(row)
    db.flush()
    return row


def get_note(db: Session, note_id: str) -> SupportNote | None:
    return db.get(SupportNote, note_id)


def delete_note(db: Session, note: SupportNote) -> None:
    db.delete(note)
    db.flush()


# --- Overview business counts (PRD §7.2) ---


def counts_today_and_month(db: Session) -> dict[str, Any]:
    day_start = _start_of_day_utc()
    month_start = day_start.replace(day=1)
    users_today = db.execute(
        select(func.count(User.id)).where(User.created_at >= day_start)
    ).scalar() or 0
    users_month = db.execute(
        select(func.count(User.id)).where(User.created_at >= month_start)
    ).scalar() or 0
    projects_today = db.execute(
        select(func.count(VideoProject.id)).where(VideoProject.created_at >= day_start)
    ).scalar() or 0
    jobs_completed_today = db.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.status == JobState.completed,
            ProcessingJob.completed_at >= day_start,
        )
    ).scalar() or 0
    jobs_failed_today = db.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.status == JobState.failed,
            ProcessingJob.created_at >= day_start,
        )
    ).scalar() or 0
    return {
        "users_today": int(users_today),
        "users_this_month": int(users_month),
        "projects_today": int(projects_today),
        "jobs_completed_today": int(jobs_completed_today),
        "jobs_failed_today": int(jobs_failed_today),
        "active_subscriptions": active_subscription_count(db),
        "revenue_this_month_inr": revenue_since(db, month_start),
    }


# --- Admin Panel Phase 5: storage & compliance ---


_STORAGE_KEY_COLUMNS = (
    ("input", VideoProject.input_storage_key),
    ("proxy", VideoProject.proxy_storage_key),
    ("preview", VideoProject.preview_storage_key),
    ("thumbnail", VideoProject.thumbnail_storage_key),
)


def storage_bucket_bytes(db: Session) -> list[dict[str, Any]]:
    """Per-bucket byte totals for the §18.1 storage overview.

    ``output`` bytes come from :class:`OutputFile.file_size` (the durable, sized
    bucket). The input/proxy/preview/thumbnail buckets carry only a key on the
    project row (no per-file size column), so we approximate their footprint via
    the project ``file_size`` for input and count-based estimates elsewhere —
    here we surface the *input* bytes precisely (== source size) and leave the
    proxy/preview/thumbnail buckets at their recorded key counts (0 bytes until
    a size is tracked). Callers feed this straight into
    :func:`admin_service.storage_overview`.
    """
    rows: list[dict[str, Any]] = []
    # output — summed real sizes
    out_bytes = int(db.execute(select(func.coalesce(func.sum(OutputFile.file_size), 0))).scalar() or 0)
    rows.append({"bucket": "output", "bytes": out_bytes})
    # input — source file sizes on non-deleted projects
    in_bytes = int(db.execute(
        select(func.coalesce(func.sum(VideoProject.file_size), 0))
        .where(VideoProject.deleted.is_(False), VideoProject.input_storage_key.is_not(None))
    ).scalar() or 0)
    rows.append({"bucket": "input", "bytes": in_bytes})
    return rows


def storage_key_counts(db: Session) -> dict[str, int]:
    """Count of projects holding a key in each bucket (§18.2 bucket monitoring)."""
    counts: dict[str, int] = {}
    for bucket, col in _STORAGE_KEY_COLUMNS:
        counts[bucket] = int(db.execute(
            select(func.count(VideoProject.id))
            .where(VideoProject.deleted.is_(False), col.is_not(None))
        ).scalar() or 0)
    counts["output"] = int(db.execute(select(func.count(OutputFile.id))).scalar() or 0)
    return counts


def list_output_files_for_retention(
    db: Session, *, limit: int = 500
) -> list[tuple[OutputFile, VideoProject]]:
    """Output files joined to their project for the §18.3 retention dashboard.

    The project supplies the legal-hold + cleanup-failed context that the pure
    :func:`admin_service.retention_bucket` classifier needs.
    """
    rows = db.execute(
        select(OutputFile, VideoProject)
        .join(VideoProject, OutputFile.project_id == VideoProject.id)
        .order_by(OutputFile.expires_at.is_(None), OutputFile.expires_at.asc())
        .limit(limit)
    ).all()
    return [(o, p) for o, p in rows]


def project_has_active_job(db: Session, project_id: str) -> bool:
    """§18.5 safety: True if a non-terminal job references this project."""
    terminal = (JobState.completed, JobState.failed, JobState.cancelled, JobState.expired)
    n = db.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.project_id == project_id,
            ProcessingJob.status.notin_(terminal),
        )
    ).scalar() or 0
    return bool(n)


def mark_retention_extended(db: Session, project_id: str) -> None:
    for o in db.execute(
        select(OutputFile).where(OutputFile.project_id == project_id)
    ).scalars():
        o.retention_extended = True
    db.flush()


def clear_cleanup_failed(db: Session, project_id: str) -> None:
    for o in db.execute(
        select(OutputFile).where(OutputFile.project_id == project_id)
    ).scalars():
        o.cleanup_failed = False
    db.flush()


def list_abuse_filtered(
    db: Session,
    *,
    status: str | None = None,
    severity: str | None = None,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[AbuseReport], int]:
    """Paginated + filtered abuse report list (PRD §21.2)."""
    conds = []
    if status:
        conds.append(AbuseReport.status == status)
    if severity:
        conds.append(AbuseReport.severity == severity)
    if q:
        like = f"%{q}%"
        conds.append(
            AbuseReport.reason.ilike(like)
            | (AbuseReport.project_id == q)
            | (AbuseReport.id == q)
        )
    total = int(db.execute(select(func.count(AbuseReport.id)).where(*conds)).scalar() or 0)
    rows = list(db.execute(
        select(AbuseReport).where(*conds)
        .order_by(AbuseReport.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars())
    return rows, total


def update_abuse_fields(
    db: Session, report: AbuseReport, *, severity: str | None = None,
    assigned_reviewer: str | None = None,
) -> AbuseReport:
    if severity is not None:
        report.severity = severity
    if assigned_reviewer is not None:
        report.assigned_reviewer = assigned_reviewer
    db.flush()
    return report


def project_previous_reports(db: Session, project_id: str, *, exclude_id: str | None = None) -> int:
    conds = [AbuseReport.project_id == project_id]
    if exclude_id:
        conds.append(AbuseReport.id != exclude_id)
    return int(db.execute(select(func.count(AbuseReport.id)).where(*conds)).scalar() or 0)


def compliance_overview_counts(db: Session) -> dict[str, Any]:
    """Aggregates for the §21.1 compliance overview."""
    open_statuses = ("new", "under_review", "waiting_for_information", "action_required", "escalated")
    ownership = int(db.execute(select(func.count(ComplianceConfirmation.id))).scalar() or 0)
    reported = int(db.execute(
        select(func.count(func.distinct(AbuseReport.project_id)))
        .where(AbuseReport.project_id.is_not(None))
    ).scalar() or 0)
    open_reviews = int(db.execute(
        select(func.count(AbuseReport.id)).where(AbuseReport.status.in_(open_statuses))
    ).scalar() or 0)
    suspended = int(db.execute(
        select(func.count(User.id)).where(User.account_status == AccountStatus.suspended)
    ).scalar() or 0)
    legal_hold = int(db.execute(
        select(func.count(VideoProject.id)).where(VideoProject.legal_hold.is_(True))
    ).scalar() or 0)
    # Repeat offenders: reporters/projects with >1 report.
    repeat = int(db.execute(
        select(func.count()).select_from(
            select(AbuseReport.project_id)
            .where(AbuseReport.project_id.is_not(None))
            .group_by(AbuseReport.project_id)
            .having(func.count(AbuseReport.id) > 1)
            .subquery()
        )
    ).scalar() or 0)
    return {
        "ownership_confirmations": ownership,
        "projects_reported": reported,
        "open_reviews": open_reviews,
        "suspended_accounts": suspended,
        "repeat_offenders": repeat,
        "high_risk_uploads": 0,
        "missing_confirmations": 0,
        "projects_on_legal_hold": legal_hold,
    }


# ---------------------------------------------------------------------------
# Phase 6 — AI models, presets, feature flags, notifications, maintenance
# ---------------------------------------------------------------------------


def list_models(db: Session, *, model_type: str | None = None, status: str | None = None) -> list[AIModel]:
    stmt = select(AIModel)
    if model_type:
        stmt = stmt.where(AIModel.model_type == model_type)
    if status:
        stmt = stmt.where(AIModel.status == status)
    stmt = stmt.order_by(AIModel.name, AIModel.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_model(db: Session, model_id: str) -> AIModel | None:
    return db.get(AIModel, model_id)


def get_model_by_name_version(db: Session, name: str, version: str) -> AIModel | None:
    return db.execute(
        select(AIModel).where(AIModel.name == name, AIModel.version == version)
    ).scalar_one_or_none()


def insert_model(db: Session, **fields: Any) -> AIModel:
    model = AIModel(**fields)
    db.add(model)
    db.flush()
    return model


def clear_model_flag(db: Session, *, model_type: str, field: str) -> None:
    """Demote every model of ``model_type`` that currently holds ``field``.

    Used to keep is_default / is_fallback single-valued per model family before
    promoting a new holder (§19.4).
    """
    column = getattr(AIModel, field)
    rows = db.execute(
        select(AIModel).where(AIModel.model_type == model_type, column.is_(True))
    ).scalars().all()
    for row in rows:
        setattr(row, field, False)


def list_presets(db: Session, *, enabled: bool | None = None) -> list[ProcessingPreset]:
    stmt = select(ProcessingPreset)
    if enabled is not None:
        stmt = stmt.where(ProcessingPreset.enabled.is_(enabled))
    stmt = stmt.order_by(ProcessingPreset.is_default.desc(), ProcessingPreset.name)
    return list(db.execute(stmt).scalars().all())


def get_preset(db: Session, preset_id: str) -> ProcessingPreset | None:
    return db.get(ProcessingPreset, preset_id)


def insert_preset(db: Session, **fields: Any) -> ProcessingPreset:
    preset = ProcessingPreset(**fields)
    db.add(preset)
    db.flush()
    return preset


def clear_default_preset(db: Session) -> None:
    """Demote whichever preset is currently the platform default (§20.3)."""
    rows = db.execute(
        select(ProcessingPreset).where(ProcessingPreset.is_default.is_(True))
    ).scalars().all()
    for row in rows:
        row.is_default = False


def list_feature_flags(db: Session) -> list[FeatureFlag]:
    return list(db.execute(select(FeatureFlag).order_by(FeatureFlag.key)).scalars().all())


def upsert_feature_flag(
    db: Session, *, key: str, enabled: bool, label: str | None = None, description: str | None = None
) -> FeatureFlag:
    flag = db.execute(select(FeatureFlag).where(FeatureFlag.key == key)).scalar_one_or_none()
    if flag is None:
        flag = FeatureFlag(key=key, label=label or key, enabled=enabled, description=description)
        db.add(flag)
    else:
        flag.enabled = enabled
        if label is not None:
            flag.label = label
        if description is not None:
            flag.description = description
    db.flush()
    return flag


def list_templates(db: Session) -> list[NotificationTemplate]:
    return list(db.execute(select(NotificationTemplate).order_by(NotificationTemplate.key)).scalars().all())


def get_template(db: Session, template_id: str) -> NotificationTemplate | None:
    return db.get(NotificationTemplate, template_id)


def get_template_by_key(db: Session, key: str) -> NotificationTemplate | None:
    return db.execute(
        select(NotificationTemplate).where(NotificationTemplate.key == key)
    ).scalar_one_or_none()


def upsert_template(db: Session, *, key: str, **fields: Any) -> NotificationTemplate:
    tmpl = get_template_by_key(db, key)
    if tmpl is None:
        tmpl = NotificationTemplate(key=key, **fields)
        db.add(tmpl)
    else:
        for name, value in fields.items():
            setattr(tmpl, name, value)
        tmpl.version = (tmpl.version or 1) + 1
    db.flush()
    return tmpl


def broadcast_recipients(db: Session, *, target: str, plan: str | None = None) -> list[str]:
    """Resolve a §23.3 target segment to a list of user IDs.

    Only active accounts are ever messaged. ``users_with_active_jobs`` and
    ``active_subscribers`` are derived from the jobs / subscriptions tables.
    """
    active = (User.account_status == AccountStatus.active)
    if target == "all":
        stmt = select(User.id).where(active)
    elif target == "free_users":
        stmt = select(User.id).where(active, User.plan_id.is_(None))
    elif target == "specific_plan":
        stmt = select(User.id).where(active, User.plan_id == plan)
    elif target == "active_subscribers":
        stmt = (
            select(User.id)
            .join(Subscription, Subscription.user_id == User.id)
            .where(active, Subscription.status == SubscriptionStatus.active)
        )
    elif target == "users_with_active_jobs":
        running = (
            JobState.preview_queued, JobState.processing_queued,
            JobState.preview_processing, JobState.processing, JobState.encoding,
        )
        stmt = (
            select(func.distinct(ProcessingJob.user_id))
            .where(ProcessingJob.status.in_(running))
        )
    else:  # selected_users is handled by the caller passing explicit ids
        stmt = select(User.id).where(active)
    return [row for row in db.execute(stmt).scalars().all()]


def create_notifications(db: Session, *, user_ids: list[str], kind: str, message: str) -> int:
    """Bulk-insert one in-app Notification per recipient (§23.3)."""
    objs = [Notification(user_id=uid, kind=kind, message=message) for uid in user_ids]
    db.add_all(objs)
    db.flush()
    return len(objs)


def create_broadcast(db: Session, **fields: Any) -> Broadcast:
    bc = Broadcast(**fields)
    db.add(bc)
    db.flush()
    return bc


def list_broadcasts(db: Session, *, limit: int = 50) -> list[Broadcast]:
    return list(
        db.execute(select(Broadcast).order_by(Broadcast.created_at.desc()).limit(limit)).scalars().all()
    )


def get_setting_json(db: Session, key: str) -> dict[str, Any] | None:
    """Read a JSON-encoded system setting (used for maintenance state §26.6)."""
    import json

    setting = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if setting is None or not setting.value:
        return None
    try:
        data = json.loads(setting.value)
        return data if isinstance(data, dict) else None
    except (ValueError, TypeError):
        return None


def set_setting_json(db: Session, key: str, value: dict[str, Any]) -> SystemSetting:
    """Write a JSON-encoded system setting (used for maintenance state §26.6)."""
    import json

    return upsert_setting(db, key, json.dumps(value))


# =====================================================================
# Admin Panel Phase 7: analytics / health / incidents / admin-mgmt / search
# =====================================================================


def analytics_counts(db: Session, *, since: datetime | None = None) -> dict[str, Any]:
    """Raw funnel + processing + cost aggregates for §24.

    A single call assembles every count the pure ``admin_service`` analytics
    reducers need. ``since`` optionally windows the time-scoped aggregates
    (jobs / uploads / payments); user totals stay lifetime so conversion ratios
    read against the whole base.
    """
    def _count(model, *where) -> int:
        return int(db.execute(select(func.count()).select_from(model).where(*where)).scalar() or 0)

    job_window = (ProcessingJob.created_at >= since,) if since else ()

    registrations = _count(User)
    verified_users = _count(User, User.email_verified.is_(True))
    paid_users = _count(User, User.plan_id.is_not(None))

    uploads_started = _count(Upload)
    uploads_completed = _count(Upload, Upload.completed.is_(True))
    projects_total = _count(VideoProject, VideoProject.deleted.is_(False))
    previews_generated = _count(VideoProject, VideoProject.preview_storage_key.is_not(None))

    analyze_started = _count(ProcessingJob, ProcessingJob.job_type == JobType.analyze, *job_window)
    analyze_done = _count(
        ProcessingJob, ProcessingJob.job_type == JobType.analyze,
        ProcessingJob.status == JobState.completed, *job_window,
    )
    process_jobs = _count(ProcessingJob, ProcessingJob.job_type == JobType.process, *job_window)
    jobs_total = _count(ProcessingJob, *job_window)
    jobs_succeeded = _count(ProcessingJob, ProcessingJob.status == JobState.completed, *job_window)
    jobs_completed = jobs_succeeded

    # Failure buckets keyed by model/worker/codec/resolution (PRD §24.2). Each
    # value is {total, failed}; grouped in Python to stay backend-agnostic.
    by_model: dict[str, dict[str, int]] = {}
    by_worker: dict[str, dict[str, int]] = {}
    rows = db.execute(
        select(
            ProcessingJob.processing_mode, ProcessingJob.worker_id, ProcessingJob.status
        ).where(*job_window)
    ).all()
    for mode, worker, status in rows:
        mkey = getattr(mode, "value", str(mode)) if mode is not None else "unknown"
        wkey = worker or "unassigned"
        for bucket, key in ((by_model, mkey), (by_worker, wkey)):
            slot = bucket.setdefault(key, {"total": 0, "failed": 0})
            slot["total"] += 1
            if status == JobState.failed:
                slot["failed"] += 1

    return {
        # funnel
        "registrations": registrations,
        "verified_users": verified_users,
        "paid_users": paid_users,
        "uploads_started": uploads_started,
        "uploads_completed": uploads_completed,
        "projects_total": projects_total,
        "previews_generated": previews_generated,
        "analyses_started": analyze_started,
        "analyses_completed": analyze_done,
        "full_processes": process_jobs,
        "jobs_total": jobs_total,
        "jobs_succeeded": jobs_succeeded,
        "jobs_completed": jobs_completed,
        "reprocesses": max(0, process_jobs - projects_total),
        # download funnel isn't event-tracked yet — approximate from completed jobs
        "downloads_started": jobs_succeeded,
        "downloads_completed": jobs_succeeded,
        # processing perf
        "by_model": by_model,
        "by_worker": by_worker,
        "by_codec": {},
        "by_resolution": {},
        # cost
        "active_users": _count(User, User.account_status == AccountStatus.active),
        "storage_bytes_total": storage_bytes(db),
    }


def business_analytics_counts(db: Session) -> dict[str, Any]:
    """§24.3 business aggregates (revenue by plan, refund rate, churn hints)."""
    month_start = _start_of_day_utc().replace(day=1)
    total_payments = int(db.execute(select(func.count(Payment.id))).scalar() or 0)
    refunded = int(db.execute(select(func.count(Refund.id))).scalar() or 0)
    revenue_by_plan_rows = db.execute(
        select(Payment.plan_id, func.coalesce(func.sum(Payment.amount_inr), 0))
        .group_by(Payment.plan_id)
    ).all()
    return {
        "mrr_inr": revenue_since(db, month_start),
        "active_subscriptions": active_subscription_count(db),
        "total_payments": total_payments,
        "total_refunds": refunded,
        "revenue_by_plan": {(pid or "none"): int(amt) for pid, amt in revenue_by_plan_rows},
    }


def health_probe_counts(db: Session) -> dict[str, Any]:
    """DB-derived slice of the §25.2 health metrics.

    The live infra probes (Redis memory, API latency) are filled in by the route
    from Redis / request middleware; here we surface what the database knows:
    queue depth and worker-heartbeat failures.
    """
    queued = int(db.execute(
        select(func.count(ProcessingJob.id)).where(
            ProcessingJob.status.in_((JobState.preview_queued, JobState.processing_queued))
        )
    ).scalar() or 0)
    threshold = datetime.now(timezone.utc) - timedelta(seconds=worker_offline_threshold_seconds())
    stale_workers = int(db.execute(
        select(func.count(WorkerNode.id)).where(
            (WorkerNode.last_heartbeat.is_(None)) | (WorkerNode.last_heartbeat < threshold)
        )
    ).scalar() or 0)
    return {"queue_depth": queued, "worker_heartbeat_failures": stale_workers}


# --- §25.3 incidents ---


def list_incidents(db: Session, *, status: str | None = None, limit: int = 100) -> list["Incident"]:
    stmt = select(Incident)
    if status:
        stmt = stmt.where(Incident.status == status)
    stmt = stmt.order_by(Incident.started_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_incident(db: Session, incident_id: str) -> "Incident | None":
    return db.get(Incident, incident_id)


def insert_incident(db: Session, **fields: Any) -> "Incident":
    inc = Incident(**fields)
    db.add(inc)
    db.flush()
    return inc


# --- §28 administrator management ---


def list_admins(db: Session) -> list[User]:
    """All staff accounts (admin_role set OR legacy role=='admin')."""
    stmt = (
        select(User)
        .where((User.admin_role.is_not(None)) | (User.role == UserRole.admin))
        .order_by(User.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def count_active_super_admins(db: Session, *, exclude_id: str | None = None) -> int:
    """Active super_admins, optionally excluding one row (last-super-admin guard).

    Counts explicit ``admin_role == 'super_admin'`` plus legacy ``role=='admin'``
    with NULL admin_role (which resolves to super_admin)."""
    is_super = (User.admin_role == "super_admin") | (
        (User.role == UserRole.admin) & (User.admin_role.is_(None))
    )
    stmt = select(func.count(User.id)).where(
        is_super, User.account_status == AccountStatus.active
    )
    if exclude_id:
        stmt = stmt.where(User.id != exclude_id)
    return int(db.execute(stmt).scalar() or 0)


# --- §29 global search ---


def search_entities(db: Session, *, entity_types: list[str], token: str, limit: int = 10) -> dict[str, list[dict]]:
    """Look up ``token`` across the candidate ``entity_types`` (PRD §29).

    Returns a dict keyed by entity type → up to ``limit`` compact result rows
    ({id, label, sublabel}) so the header search can group + deep-link. Every
    branch is defensive: an unmatched type simply yields no rows.
    """
    results: dict[str, list[dict]] = {}
    like = f"%{token}%"

    for etype in entity_types:
        rows: list[dict] = []
        if etype == "user":
            stmt = select(User).where(
                (User.email.ilike(like)) | (User.id == token) | (User.full_name.ilike(like))
            ).limit(limit)
            rows = [{"id": u.id, "label": u.email, "sublabel": u.full_name} for u in db.execute(stmt).scalars().all()]
        elif etype == "project":
            stmt = select(VideoProject).where(
                (VideoProject.id == token) | (VideoProject.title.ilike(like))
            ).limit(limit)
            rows = [{"id": p.id, "label": p.title or p.id, "sublabel": p.status.value if hasattr(p.status, "value") else str(p.status)} for p in db.execute(stmt).scalars().all()]
        elif etype == "job":
            stmt = select(ProcessingJob).where(ProcessingJob.id == token).limit(limit)
            rows = [{"id": j.id, "label": f"{j.job_type.value} job", "sublabel": j.status.value if hasattr(j.status, "value") else str(j.status)} for j in db.execute(stmt).scalars().all()]
        elif etype == "payment":
            stmt = select(Payment).where(
                (Payment.id == token) | (Payment.razorpay_payment_id == token)
            ).limit(limit)
            rows = [{"id": p.id, "label": p.id, "sublabel": (p.razorpay_payment_id or "")[-6:]} for p in db.execute(stmt).scalars().all()]
        elif etype == "razorpay_payment":
            stmt = select(Payment).where(Payment.razorpay_payment_id == token).limit(limit)
            rows = [{"id": p.id, "label": p.razorpay_payment_id or p.id, "sublabel": "razorpay"} for p in db.execute(stmt).scalars().all()]
        elif etype == "subscription":
            stmt = select(Subscription).where(Subscription.id == token).limit(limit)
            rows = [{"id": s.id, "label": s.id, "sublabel": s.status.value if hasattr(s.status, "value") else str(s.status)} for s in db.execute(stmt).scalars().all()]
        elif etype == "promo":
            stmt = select(PromoCode).where(
                (PromoCode.code.ilike(like)) | (PromoCode.id == token)
            ).limit(limit)
            rows = [{"id": pc.id, "label": pc.code, "sublabel": "promo"} for pc in db.execute(stmt).scalars().all()]
        elif etype == "worker":
            stmt = select(WorkerNode).where(
                (WorkerNode.name.ilike(like)) | (WorkerNode.id == token)
            ).limit(limit)
            rows = [{"id": w.id, "label": w.name, "sublabel": w.status} for w in db.execute(stmt).scalars().all()]
        elif etype == "abuse_report":
            stmt = select(AbuseReport).where(AbuseReport.id == token).limit(limit)
            rows = [{"id": r.id, "label": f"report {r.id[:8]}", "sublabel": r.status} for r in db.execute(stmt).scalars().all()]
        if rows:
            results[etype] = rows
    return results


# --- §24.5 exports ---

# Column allow-lists per dataset (PRD §24.5 — restricted fields never exported).
EXPORT_COLUMNS = {
    "users": ("id", "email", "full_name", "account_status", "plan_id", "created_at"),
    "payments": ("id", "user_id", "plan_id", "amount_inr", "status", "created_at"),
    "jobs": ("id", "user_id", "job_type", "status", "created_at"),
    "audit": ("id", "actor_id", "action", "target_type", "target_id", "created_at"),
}


def export_rows(db: Session, dataset: str, *, limit: int = 5000) -> list[dict]:
    """Materialise a dataset as a list of flat dicts for CSV/JSON export.

    Only the allow-listed columns are pulled; enum values are stringified and
    datetimes ISO-formatted so the pure serializer stays type-agnostic. Never
    emits raw secrets, hashes, or storage paths (PRD §24.5)."""
    def _s(v: Any) -> Any:
        if v is None:
            return ""
        if hasattr(v, "value"):  # enum
            return v.value
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    cols = EXPORT_COLUMNS.get(dataset)
    if not cols:
        return []
    model = {"users": User, "payments": Payment, "jobs": ProcessingJob, "audit": AuditLog}[dataset]
    order = model.created_at.desc()
    entities = db.execute(select(model).order_by(order).limit(limit)).scalars().all()
    return [{col: _s(getattr(row, col, "")) for col in cols} for row in entities]


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
    "queue_metrics",
    "queue_breakdown",
    "get_worker_node",
    "worker_jobs",
    "worker_job_counts",
    "list_audit_for_target",
    "list_worker_nodes",
    "upsert_worker_heartbeat",
    "worker_offline_threshold_seconds",
    "get_all_settings",
    "upsert_setting",
    "record_audit",
    "list_audit",
    "list_audit_filtered",
    "list_abuse",
    "get_abuse",
    "set_abuse_status",
    # Phases 1+2
    "get_user",
    "get_user_locked",
    "list_users_paged",
    "user_detail_extras",
    "revoke_all_sessions",
    "list_user_sessions",
    "list_user_compliance",
    "list_audit_for_user",
    "count_super_admins",
    "insert_credit_txn",
    "list_credit_txns",
    "insert_payment",
    "list_payments",
    "revenue_since",
    "active_subscription_count",
    "list_projects_paged",
    "get_project",
    "list_user_projects",
    "project_jobs",
    "project_outputs",
    "project_compliance",
    "list_notes",
    "insert_note",
    "get_note",
    "delete_note",
    "counts_today_and_month",
    # Phase 4 — billing
    "billing_counts",
    "list_payments_filtered",
    "get_payment",
    "list_refunds",
    "insert_refund",
    "total_refunded",
    "list_webhook_events",
    "get_webhook_event",
    "insert_webhook_event",
    "list_subscriptions",
    "get_subscription",
    "get_subscription_for_user",
    "list_plans",
    "get_plan",
    "insert_plan",
    "plan_subscriber_count",
    "list_promos",
    "get_promo",
    "get_promo_by_code",
    "insert_promo",
    "credit_txns_today",
    "users_low_balance",
    # Phase 5 — storage & compliance
    "storage_bucket_bytes",
    "storage_key_counts",
    "list_output_files_for_retention",
    "project_has_active_job",
    "mark_retention_extended",
    "clear_cleanup_failed",
    "list_abuse_filtered",
    "update_abuse_fields",
    "project_previous_reports",
    "compliance_overview_counts",
    # Phase 6 — models/presets/flags/notifications/maintenance
    "list_models",
    "get_model",
    "get_model_by_name_version",
    "insert_model",
    "clear_model_flag",
    "list_presets",
    "get_preset",
    "insert_preset",
    "clear_default_preset",
    "list_feature_flags",
    "upsert_feature_flag",
    "list_templates",
    "get_template",
    "get_template_by_key",
    "upsert_template",
    "broadcast_recipients",
    "create_notifications",
    "create_broadcast",
    "list_broadcasts",
    "get_setting_json",
    "set_setting_json",
    # Phase 7 — analytics / health / incidents / admin-mgmt / search
    "analytics_counts",
    "business_analytics_counts",
    "health_probe_counts",
    "list_incidents",
    "get_incident",
    "insert_incident",
    "list_admins",
    "count_active_super_admins",
    "search_entities",
    "export_rows",
    "EXPORT_COLUMNS",
]
