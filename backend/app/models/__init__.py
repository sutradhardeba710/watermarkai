"""SQLAlchemy ORM models (declarative). Mirrors PRD §14 / SRS §8 schema.

MVP-critical tables are fully modeled; auxiliary tables (notifications,
audit_logs, abuse_reports, system_settings) are included so the baseline
migration creates them, even where their features land in later phases.
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
    String,
    Text,
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
    account_status: Mapped[AccountStatus] = mapped_column(
        SAEnum(AccountStatus), default=AccountStatus.active, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list[Session]] = relationship(back_populates="user", cascade="all, delete-orphan")


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
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AbuseReport(Base):
    __tablename__ = "abuse_reports"

    id: Mapped[str] = _uuid_pk()
    project_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    reported_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[str] = _uuid_pk()
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
