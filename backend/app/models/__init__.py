"""SQLAlchemy ORM models (declarative). Mirrors PRD §14 / SRS §8 schema.

MVP-critical tables are fully modeled; auxiliary tables (notifications,
audit_logs, abuse_reports, system_settings) are included so the baseline
migration creates them, even where their features land in later phases.

Payment tables (Phase 6 billing):
  Plan            — static plan catalog seeded at startup
  Subscription    — per-user Razorpay subscription record
  CreditLedger    — daily credit balance + reset tracking
"""
from __future__ import annotations

import enum
import uuid as _uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))


# --- Enums (SRS DB-004, PROCESS-002) ---


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class AdminRole(str, enum.Enum):
    """Admin-panel roles (PRD §5). Stored as a plain String(32) column —
    NOT a Postgres enum — so future roles need no ALTER TYPE migration.
    Validation happens at the app layer (services/admin_permissions.py)."""

    super_admin = "super_admin"
    operations = "operations"
    support = "support"
    billing = "billing"
    compliance = "compliance"
    analyst = "analyst"


class AccountStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    deleted = "deleted"


class ProjectStatus(str, enum.Enum):
    created = "created"
    uploading = "uploading"
    uploaded = "uploaded"
    analyzing = "analyzing"
    awaiting_review = "awaiting_review"
    preview_queued = "preview_queued"
    preview_processing = "preview_processing"
    preview_ready = "preview_ready"
    processing_queued = "processing_queued"
    processing = "processing"
    encoding = "encoding"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    expired = "expired"


class JobState(str, enum.Enum):
    created = "created"
    uploading = "uploading"
    uploaded = "uploaded"
    analyzing = "analyzing"
    awaiting_review = "awaiting_review"
    preview_queued = "preview_queued"
    preview_processing = "preview_processing"
    preview_ready = "preview_ready"
    processing_queued = "processing_queued"
    processing = "processing"
    encoding = "encoding"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    expired = "expired"


class JobType(str, enum.Enum):
    analyze = "analyze"
    track = "track"
    preview = "preview"
    process = "process"
    encode = "encode"


class QualityMode(str, enum.Enum):
    fast = "fast"
    balanced = "balanced"
    high = "high"


# --- Models ---


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.user, nullable=False)
    # Admin-panel role (PRD §5); plain string validated app-side. NULL for
    # non-staff. Legacy role=='admin' with NULL admin_role maps to super_admin
    # via admin_permissions.effective_admin_role.
    admin_role: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    # Self-service profile picture. Stores the object key inside the `avatars`
    # bucket; NULL → fall back to the generated initial/gradient avatar.
    avatar_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Administrator-management tracking (PRD §28.1). All nullable — only staff
    # rows populate them; normal users leave them NULL.
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    admin_invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    account_status: Mapped[AccountStatus] = mapped_column(
        SAEnum(AccountStatus), default=AccountStatus.active, nullable=False
    )
    # Billing — plan_id FK populated on first subscription; NULL → free plan.
    plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Denormalized daily credit balance; refreshed by the credit-reset task.
    credits_remaining: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list[Session]] = relationship(back_populates="user", cascade="all, delete-orphan")
    plan: Mapped[Plan | None] = relationship("Plan", foreign_keys=[plan_id])
    subscription: Mapped[Subscription | None] = relationship(
        "Subscription", back_populates="user", uselist=False
    )
    credit_ledger: Mapped[CreditLedger | None] = relationship(
        "CreditLedger", back_populates="user", uselist=False
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")


class VideoProject(Base):
    __tablename__ = "video_projects"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    input_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    output_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    preview_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus), default=ProjectStatus.created, index=True, nullable=False
    )
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_audio: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proxy_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Admin moderation (PRD §9.5): locked projects reject processing/downloads.
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    moderation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Compliance controls (PRD §18.5, §21.5). Legal hold blocks retention cleanup
    # and file deletion; the other two are softer moderation gates.
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_restricted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    downloads_disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    @property
    def progress(self) -> int:
        # Coarse bucket from project status; the live percentage (PROCESS-003)
        # lives on ProcessingJob and is read via the /jobs/{id}/events SSE stream.
        # Kept here so the dashboard renders a sane bar without a DB round-trip.
        buckets = {
            ProjectStatus.created: 0,
            ProjectStatus.uploading: 5,
            ProjectStatus.uploaded: 20,
            ProjectStatus.analyzing: 30,
            ProjectStatus.awaiting_review: 40,
            ProjectStatus.preview_queued: 45,
            ProjectStatus.preview_processing: 50,
            ProjectStatus.preview_ready: 55,
            ProjectStatus.processing_queued: 60,
            ProjectStatus.processing: 75,
            ProjectStatus.encoding: 90,
            ProjectStatus.completed: 100,
            ProjectStatus.failed: 0,
            ProjectStatus.cancelled: 0,
            ProjectStatus.expired: 0,
        }
        return buckets.get(self.status, 0)


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = _uuid_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("video_projects.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    total_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WatermarkCandidate(Base):
    __tablename__ = "watermark_candidates"

    id: Mapped[str] = _uuid_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("video_projects.id", ondelete="CASCADE"), index=True, nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(64), nullable=False)  # logo | text | timestamp ...
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_static: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bounding_box: Mapped[dict] = mapped_column(JSON, nullable=False)  # {x,y,w,h}
    mask_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    tracking_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    user_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WatermarkMask(Base):
    __tablename__ = "watermark_masks"

    id: Mapped[str] = _uuid_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("video_projects.id", ondelete="CASCADE"), index=True, nullable=False)
    tool: Mapped[str] = mapped_column(String(32), nullable=False)  # rectangle | polygon | brush
    geometry: Mapped[dict] = mapped_column(JSON, nullable=False)  # coords in proxy or source space
    width: Mapped[int] = mapped_column(Integer, nullable=False)  # frame width geometry refers to
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    mask_expansion: Mapped[int] = mapped_column(Integer, default=0)
    mask_feathering: Mapped[int] = mapped_column(Integer, default=4)
    temporal_smoothing: Mapped[bool] = mapped_column(Boolean, default=False)
    apply_to_entire: Mapped[bool] = mapped_column(Boolean, default=True)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = _uuid_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("video_projects.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    job_type: Mapped[JobType] = mapped_column(SAEnum(JobType), nullable=False)
    status: Mapped[JobState] = mapped_column(SAEnum(JobState), default=JobState.created, index=True, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_mode: Mapped[QualityMode] = mapped_column(SAEnum(QualityMode), default=QualityMode.balanced, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    frames_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_frames: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ProcessingSetting(Base):
    __tablename__ = "processing_settings"

    id: Mapped[str] = _uuid_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("video_projects.id", ondelete="CASCADE"), index=True, nullable=False)
    quality_mode: Mapped[QualityMode] = mapped_column(SAEnum(QualityMode), default=QualityMode.balanced, nullable=False)
    mask_expansion: Mapped[int] = mapped_column(Integer, default=0)
    mask_feathering: Mapped[int] = mapped_column(Integer, default=4)
    temporal_smoothing: Mapped[bool] = mapped_column(Boolean, default=False)
    output_resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    output_codec: Mapped[str] = mapped_column(String(32), default="libx264")
    preserve_audio: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutputFile(Base):
    __tablename__ = "output_files"

    id: Mapped[str] = _uuid_pk()
    project_id: Mapped[str] = mapped_column(ForeignKey("video_projects.id", ondelete="CASCADE"), index=True, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    bucket: Mapped[str] = mapped_column(String(64), default="outputs", nullable=False)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_mode: Mapped[QualityMode] = mapped_column(SAEnum(QualityMode), default=QualityMode.balanced, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    # Retention dashboard (PRD §18.3): a cleanup attempt that errored leaves the
    # row flagged so an admin can retry it; extended pushes expiry out.
    cleanup_failed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retention_extended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ComplianceConfirmation(Base):
    __tablename__ = "compliance_confirmations"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("video_projects.id", ondelete="CASCADE"), index=True, nullable=False)
    confirmation_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkerNode(Base):
    __tablename__ = "worker_nodes"

    id: Mapped[str] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="idle", index=True, nullable=False)
    gpu_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gpu_memory: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    software_version: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = _uuid_pk()
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # PRD §27.2 traceability — before/after snapshots + request context.
    previous_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(16), default="success", server_default="success", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class AbuseReport(Base):
    __tablename__ = "abuse_reports"

    id: Mapped[str] = _uuid_pk()
    project_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    reported_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True, nullable=False)
    # Compliance triage (PRD §21.2). Severity + reviewer assignment + resolution.
    severity: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    assigned_reviewer: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[str] = _uuid_pk()
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# --- Billing / Payment models (Phase 6) ---


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    past_due = "past_due"
    cancelled = "cancelled"
    trialing = "trialing"
    paused = "paused"
    pending = "pending"
    expired = "expired"
    completed = "completed"


class Plan(Base):
    """Static plan catalog. Seeded at startup; admin-editable via PRD §15."""

    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # 'free' | 'starter' | 'pro'
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    price_inr: Mapped[int] = mapped_column(Integer, nullable=False)          # monthly price in INR paise
    credits_per_day: Mapped[int] = mapped_column(Integer, nullable=False)     # daily credit allowance
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # e.g. plan_XXXXXXXX
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # --- Admin plan management (PRD §15.2); all nullable so existing rows are valid ---
    annual_price_inr: Mapped[int | None] = mapped_column(Integer, nullable=True)   # paise
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(16), default="monthly", nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    monthly_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_upload_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)   # e.g. '1080p'
    concurrent_jobs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_allowance_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    api_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    support_level: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Subscription(Base):
    """Per-user Razorpay subscription record."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), nullable=False)
    razorpay_subscription_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus), default=SubscriptionStatus.active, nullable=False
    )
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # --- Admin subscription management (PRD §14) ---
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payment_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credits_allocated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="subscription")
    plan: Mapped[Plan] = relationship("Plan")


class CreditLedger(Base):
    """Daily credit balance tracker. One row per user; reset by cron task."""

    __tablename__ = "credit_ledger"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    credits_used_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    credits_limit: Mapped[int] = mapped_column(Integer, default=500, nullable=False)  # mirrors plan
    last_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="credit_ledger")


class PromoCode(Base):
    """Promo codes that map to Razorpay Offers."""

    __tablename__ = "promo_codes"

    id: Mapped[str] = _uuid_pk()
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    razorpay_offer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # --- Admin promo management (PRD §16.1); all nullable/defaulted ---
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    discount_type: Mapped[str] = mapped_column(String(24), default="percentage", nullable=False)
    discount_value: Mapped[int | None] = mapped_column(Integer, nullable=True)   # amount(paise) | percent | credits
    max_discount_inr: Mapped[int | None] = mapped_column(Integer, nullable=True)  # paise
    applicable_plans: Mapped[list | None] = mapped_column(JSON, nullable=True)    # list[plan_id] or null=all
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_total_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_uses_per_user: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_purchase_inr: Mapped[int | None] = mapped_column(Integer, nullable=True)  # paise
    new_users_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sandbox_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    times_redeemed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# --- Admin panel models (PRD Phases 1+2) ---


class CreditTransaction(Base):
    """Immutable credit ledger entry (PRD §17.2). Every credit mutation —
    admin adjustment, job deduction, refund, plan allocation — writes one row.
    No updated_at: rows are never edited. Balance itself stays denormalized on
    ``users.credits_remaining``; ``balance_before``/``balance_after`` capture
    the transition for traceability."""

    __tablename__ = "credit_transactions"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # always positive
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # 'credit' | 'debit'
    balance_before: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # admin|job|refund|subscription|reset
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Payment(Base):
    """Payment history row (PRD §13). Written from Razorpay webhook events;
    sandbox subscriptions record a synthetic captured row."""

    __tablename__ = "payments"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    subscription_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    amount_inr: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # captured|failed|refunded
    method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    # --- Admin payment detail (PRD §13.2); all nullable/defaulted ---
    discount_inr: Mapped[int] = mapped_column(Integer, default=0, nullable=False)   # paise
    tax_inr: Mapped[int] = mapped_column(Integer, default=0, nullable=False)        # paise
    razorpay_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    promo_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    credits_issued: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_status: Mapped[str | None] = mapped_column(String(24), nullable=True)   # none|partial|full
    refunded_inr: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # paise
    manual_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Refund(Base):
    """Refund record (PRD §13.5). One row per refund issued against a payment.
    Refunds above a configurable amount require super-admin approval — the
    policy lives in ``app.services.admin_service.refund_requires_approval``."""

    __tablename__ = "refunds"

    id: Mapped[str] = _uuid_pk()
    payment_id: Mapped[str] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    amount_inr: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    kind: Mapped[str] = mapped_column(String(16), nullable=False)     # full | partial
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    razorpay_refund_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="processed", nullable=False)
    admin_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class WebhookEvent(Base):
    """Razorpay webhook event log (PRD §13.4 / §26). Every inbound webhook is
    recorded so admins can inspect and reprocess. ``payload`` is the raw JSON
    body; sensitive fields are masked before display, never at rest here."""

    __tablename__ = "webhook_events"

    id: Mapped[str] = _uuid_pk()
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    razorpay_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    subscription_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="processed", nullable=False)  # processed|failed|reprocessed
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class SupportNote(Base):
    """Internal admin note attached to a user and optionally a project
    (PRD §22). Visible only in the admin panel."""

    __tablename__ = "support_notes"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# --- Admin Panel Phase 6: AI models, presets, feature flags, notifications ---
#
# Status/type/strategy fields are plain String columns (not Postgres enums), in
# the same spirit as AdminRole — new values need no ALTER TYPE. The str-enums
# below are app-layer vocabularies used for validation in admin_service.


class ModelStatus(str, enum.Enum):
    active = "active"
    testing = "testing"
    disabled = "disabled"
    deprecated = "deprecated"
    maintenance = "maintenance"
    rollback_candidate = "rollback_candidate"


class AIModel(Base):
    """A registered AI model version (PRD §19). One row per name+version."""

    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_ai_models_name_version"),)

    id: Mapped[str] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="testing", index=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deployment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supported_job_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    supported_resolutions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    min_gpu_memory_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_speed_fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    failure_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Staged rollout (§19.5): internal | selected_users | percentage | plans | full
    rollout_strategy: Mapped[str] = mapped_column(String(32), default="internal", nullable=False)
    rollout_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rollout_plans: Mapped[list | None] = mapped_column(JSON, nullable=True)
    compatible_workers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    previous_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProcessingPreset(Base):
    """A named processing profile wiring models + encoding params (PRD §20)."""

    __tablename__ = "processing_presets"

    id: Mapped[str] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    required_plan: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detection_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tracking_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    inpainting_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    frame_sampling_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temporal_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mask_expansion: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    feathering: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    temporal_smoothing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    encoding_codec: Mapped[str] = mapped_column(String(32), default="libx264", nullable=False)
    encoding_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_credit_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    worker_requirements: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    estimated_relative_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FeatureFlag(Base):
    """A toggleable platform capability (PRD §26.5)."""

    __tablename__ = "feature_flags"

    id: Mapped[str] = _uuid_pk()
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NotificationTemplate(Base):
    """An editable email/in-app template (PRD §23.1/§23.2)."""

    __tablename__ = "notification_templates"

    id: Mapped[str] = _uuid_pk()
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    html_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    variables: Mapped[list | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Broadcast(Base):
    """A one-off broadcast announcement to a user segment (PRD §23.3)."""

    __tablename__ = "broadcasts"

    id: Mapped[str] = _uuid_pk()
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # in_app|maintenance|feature|billing|policy
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(String(32), default="all", nullable=False)
    target_plan: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recipient_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Incident(Base):
    """A system-health incident on the timeline (PRD §25.3).

    Rows are opened by the metrics/alerting path or by an administrator, then
    acknowledged / annotated / resolved. ``notes`` accumulates a JSON list of
    ``{at, admin_id, text}`` entries so the timeline keeps its history.
    """

    __tablename__ = "incidents"

    id: Mapped[str] = _uuid_pk()
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="minor", nullable=False)  # info|minor|major|critical
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False, index=True)  # open|monitoring|resolved
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    silenced_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
