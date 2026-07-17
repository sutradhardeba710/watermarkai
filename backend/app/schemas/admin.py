"""Admin schemas (SRS ADMIN-001..007, MON-001..004, STORAGE-006, RECON-008).

Pydantic models for the Phase 8 admin surface. Pure logic — no ORM imports —
so the validators (config overrides, audit shape, retention policy) stay
unit-testable on the 32-bit dev box without SQLAlchemy.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# --- ADMIN-001 Overview ---


class AdminOverview(BaseModel):
    total_users: int
    active_users: int
    suspended_users: int
    jobs_today: int
    queue_length: int
    completed_jobs: int
    failed_jobs: int
    gpu_workers: int
    storage_bytes: int
    avg_processing_seconds: Optional[float] = None


# --- ADMIN-002 User management ---


class AdminUser(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    account_status: str
    email_verified: bool
    created_at: datetime
    project_count: int = 0
    job_count: int = 0

    model_config = {"from_attributes": True}


class UserActionRequest(BaseModel):
    """ADMIN-002 suspend / reactivate body."""
    action: str = Field(description="suspend | reactivate")

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in ("suspend", "reactivate"):
            raise ValueError("action must be 'suspend' or 'reactivate'")
        return v


class UserActionResponse(BaseModel):
    id: str
    account_status: str


# --- ADMIN-003 Job management ---


class AdminJob(BaseModel):
    id: str
    project_id: str
    user_id: str
    job_type: str
    status: str
    progress: int
    current_stage: Optional[str] = None
    processing_mode: str
    worker_id: Optional[str] = None
    attempt_count: int = 0
    frames_processed: int = 0
    total_frames: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobActionRequest(BaseModel):
    """ADMIN-003 retry | cancel body."""
    action: str

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in ("retry", "cancel"):
            raise ValueError("action must be 'retry' or 'cancel'")
        return v


class JobActionResponse(BaseModel):
    id: str
    status: str


# --- ADMIN-004 Worker monitoring ---


class WorkerInfo(BaseModel):
    name: str
    online: bool
    status: Optional[str] = None
    gpu_name: Optional[str] = None
    gpu_memory: Optional[int] = None
    active_job_id: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    software_version: Optional[str] = None


# --- ADMIN-005 System configuration ---


class SystemConfig(BaseModel):
    """ADMIN-005 editable knobs. Mirrors Settings fields; values are strings so
    list-typed knobs (formats) survive the JSON round-trip through SystemSetting."""

    max_file_size_mb: int
    max_duration_seconds: int
    max_width: int
    max_height: int
    max_fps: int
    allowed_upload_extensions: list[str]
    retain_original_hours: int
    retain_preview_hours: int
    retain_output_days: int
    retain_failed_hours: int
    worker_concurrency: int
    max_retries: int
    enabled_models: list[str]
    maintenance_mode: bool


class SystemConfigUpdate(BaseModel):
    """Partial update for ADMIN-005. Every field optional; only provided keys
    are written to SystemSetting rows."""

    max_file_size_mb: Optional[int] = Field(default=None, ge=1, le=10240)
    max_duration_seconds: Optional[int] = Field(default=None, ge=1, le=86400)
    max_width: Optional[int] = Field(default=None, ge=1, le=7680)
    max_height: Optional[int] = Field(default=None, ge=1, le=4320)
    max_fps: Optional[int] = Field(default=None, ge=1, le=240)
    allowed_upload_extensions: Optional[list[str]] = None
    retain_original_hours: Optional[int] = Field(default=None, ge=0, le=720)
    retain_preview_hours: Optional[int] = Field(default=None, ge=0, le=720)
    retain_output_days: Optional[int] = Field(default=None, ge=0, le=365)
    retain_failed_hours: Optional[int] = Field(default=None, ge=0, le=720)
    worker_concurrency: Optional[int] = Field(default=None, ge=1, le=64)
    max_retries: Optional[int] = Field(default=None, ge=0, le=10)
    enabled_models: Optional[list[str]] = None
    maintenance_mode: Optional[bool] = None


# --- ADMIN-006 Audit logs ---


class AuditEntry(BaseModel):
    id: str
    actor_id: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    details: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- ADMIN-007 Abuse review ---


class AbuseReportSummary(BaseModel):
    id: str
    project_id: Optional[str] = None
    reported_by: Optional[str] = None
    reason: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AbuseActionRequest(BaseModel):
    action: str

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in ("dismiss", "escalate", "suspend_reporter"):
            raise ValueError("action must be 'dismiss', 'escalate', or 'suspend_reporter'")
        return v


class AbuseActionResponse(BaseModel):
    id: str
    status: str


__all__ = [
    "AdminOverview",
    "AdminUser",
    "UserActionRequest",
    "UserActionResponse",
    "AdminJob",
    "JobActionRequest",
    "JobActionResponse",
    "WorkerInfo",
    "SystemConfig",
    "SystemConfigUpdate",
    "AuditEntry",
    "AbuseReportSummary",
    "AbuseActionRequest",
    "AbuseActionResponse",
]
