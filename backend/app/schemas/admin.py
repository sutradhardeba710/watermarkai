"""Admin schemas (SRS ADMIN-001..007, MON-001..004, STORAGE-006, RECON-008).

Pydantic models for the Phase 8 admin surface. Pure logic — no ORM imports —
so the validators (config overrides, audit shape, retention policy) stay
unit-testable on the 32-bit dev box without SQLAlchemy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


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
    # PRD §7.2 additions — Optional-defaulted so pre-existing callers/tests
    # constructing the older shape stay valid.
    users_today: Optional[int] = None
    users_this_month: Optional[int] = None
    projects_today: Optional[int] = None
    jobs_completed_today: Optional[int] = None
    jobs_failed_today: Optional[int] = None
    success_rate: Optional[float] = None
    active_subscriptions: Optional[int] = None
    revenue_this_month_inr: Optional[int] = None


# --- ADMIN-002 User management ---


class AdminUser(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    admin_role: Optional[str] = None
    account_status: str
    email_verified: bool
    created_at: datetime
    plan_id: Optional[str] = None
    credits_remaining: Optional[int] = None
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
    # PRD §27.2 traceability (nullable on legacy rows).
    previous_data: Optional[dict] = None
    new_data: Optional[dict] = None
    reason: Optional[str] = None
    ip_hash: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    result: Optional[str] = None
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


# --- Admin Panel Phase 3: jobs / queues / workers deep-dive (PRD §10–12) ---


class JobStageStep(BaseModel):
    """One node in the job stage timeline (PRD §10.4)."""
    stage: str
    state: str  # done | current | pending | skipped
    label: str


class AdminJobDetail(AdminJob):
    """GET /admin/jobs/{id} — full incident bundle (PRD §10.3)."""
    project_title: Optional[str] = None
    user_email: Optional[str] = None
    duration_seconds: Optional[float] = None
    queued_seconds: Optional[float] = None
    timeline: list[JobStageStep] = []
    recent_events: list["AuditEntry"] = []


class QueueInfo(BaseModel):
    name: str
    queued: int = 0
    active: int = 0
    failed_today: int = 0
    oldest_queued_seconds: Optional[float] = None


class QueueMetrics(BaseModel):
    """GET /admin/queues (PRD §11)."""
    queued: int = 0
    active: int = 0
    completed_today: int = 0
    failed_today: int = 0
    by_state: dict[str, int] = {}
    queues: list[QueueInfo] = []


class WorkerDetail(WorkerInfo):
    """GET /admin/workers/{name} (PRD §12.3)."""
    active_job: Optional["AdminJob"] = None
    recent_jobs: list["AdminJob"] = []
    completed_count: int = 0
    failed_count: int = 0


# --- Admin Panel Phases 1+2 (PRD §5, §8, §9, §17, §22, §27) ---
# Actions on users routed through POST /admin/users/{id}/actions. Grouped by
# the permission that authorizes them (checked in the route layer).
USER_SUPPORT_ACTIONS = ("verify_email", "resend_verification", "force_password_reset", "revoke_sessions")
USER_MANAGE_ACTIONS = ("suspend", "ban", "restore")
USER_DELETE_ACTIONS = ("delete_account",)
ALL_USER_ACTIONS = USER_SUPPORT_ACTIONS + USER_MANAGE_ACTIONS + USER_DELETE_ACTIONS

PROJECT_ACTIONS = ("extend_retention", "expire_now", "lock", "unlock", "delete_files")

# Actions that must carry a reason (PRD §30.5 / §33.5).
DESTRUCTIVE_USER_ACTIONS = ("suspend", "ban", "delete_account")


class AdminMe(BaseModel):
    """GET /admin/me — powers frontend nav gating."""
    id: str
    email: str
    full_name: str
    admin_role: str
    permissions: list[str]


class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int


class AdminUserPage(PageMeta):
    items: list[AdminUser]


class AuditPage(PageMeta):
    items: list[AuditEntry]


class AdminUserActionRequest(BaseModel):
    """POST /admin/users/{id}/actions body (PRD §8.4)."""
    action: str
    reason: Optional[str] = None

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in ALL_USER_ACTIONS:
            raise ValueError(f"action must be one of {', '.join(ALL_USER_ACTIONS)}")
        return v

    @model_validator(mode="after")
    def _reason_required(self) -> "AdminUserActionRequest":
        if self.action in DESTRUCTIVE_USER_ACTIONS and not (self.reason or "").strip():
            raise ValueError(f"'{self.action}' requires a reason")
        return self


class RoleChangeRequest(BaseModel):
    """POST /admin/users/{id}/role — null clears staff access."""
    admin_role: Optional[str] = None

    @field_validator("admin_role")
    @classmethod
    def _check_role(cls, v: Optional[str]) -> Optional[str]:
        from app.services.admin_permissions import ADMIN_ROLES
        if v is not None and v not in ADMIN_ROLES:
            raise ValueError(f"admin_role must be one of {', '.join(ADMIN_ROLES)} or null")
        return v


class PlanChangeRequest(BaseModel):
    plan_id: str = Field(min_length=1, max_length=32)
    reason: Optional[str] = None


class CreditAdjustRequest(BaseModel):
    """POST /admin/users/{id}/credits (PRD §8.5: amount + reason required)."""
    amount: int = Field(ge=1)
    direction: str
    reason: str = Field(min_length=3)
    reference: Optional[str] = None  # ticket / reference number

    @field_validator("direction")
    @classmethod
    def _check_direction(cls, v: str) -> str:
        if v not in ("credit", "debit"):
            raise ValueError("direction must be 'credit' or 'debit'")
        return v


class CreditTransactionOut(BaseModel):
    id: str
    user_id: str
    amount: int
    direction: str
    balance_before: int
    balance_after: int
    reason: Optional[str] = None
    source: str
    project_id: Optional[str] = None
    job_id: Optional[str] = None
    admin_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditTxnPage(PageMeta):
    items: list[CreditTransactionOut]


class PaymentOut(BaseModel):
    id: str
    user_id: str
    subscription_id: Optional[str] = None
    plan_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    amount_inr: int
    currency: str
    status: str
    method: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SupportNoteOut(BaseModel):
    id: str
    user_id: str
    project_id: Optional[str] = None
    author_id: str
    body: str
    pinned: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SupportNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    project_id: Optional[str] = None
    pinned: bool = False


class AdminSubscriptionOut(BaseModel):
    id: str
    plan_id: str
    status: str
    razorpay_subscription_id: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime


class AdminSessionOut(BaseModel):
    id: str
    user_agent: Optional[str] = None
    ip_hash: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    revoked: bool

    model_config = {"from_attributes": True}


class AdminUserDetail(BaseModel):
    """GET /admin/users/{id} — header card + profile tab (PRD §8.3)."""
    id: str
    email: str
    full_name: str
    role: str
    admin_role: Optional[str] = None
    account_status: str
    email_verified: bool
    created_at: datetime
    plan_id: Optional[str] = None
    plan_name: Optional[str] = None
    credits_remaining: int = 0
    credits_limit: Optional[int] = None
    credits_used_today: Optional[int] = None
    project_count: int = 0
    job_count: int = 0
    failed_job_count: int = 0
    storage_bytes: int = 0
    active_session_count: int = 0
    subscription: Optional[AdminSubscriptionOut] = None


class AdminProject(BaseModel):
    """Row for GET /admin/projects (PRD §9.1)."""
    id: str
    user_id: str
    user_email: Optional[str] = None
    title: str
    original_filename: str
    status: str
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    locked: bool = False
    deleted: bool = False
    created_at: datetime
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class AdminProjectPage(PageMeta):
    items: list[AdminProject]


class AdminOutputFileOut(BaseModel):
    id: str
    storage_key: str
    bucket: str
    file_size: Optional[int] = None
    quality_mode: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class AdminComplianceOut(BaseModel):
    id: str
    confirmation_version: str
    confirmed_at: datetime
    ip_hash: Optional[str] = None

    model_config = {"from_attributes": True}


class AdminProjectDetail(AdminProject):
    """GET /admin/projects/{id} (PRD §9.4)."""
    fps: Optional[float] = None
    frame_count: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    has_audio: Optional[bool] = None
    moderation_note: Optional[str] = None
    input_storage_key: Optional[str] = None
    output_storage_key: Optional[str] = None
    preview_storage_key: Optional[str] = None
    jobs: list[AdminJob] = []
    outputs: list[AdminOutputFileOut] = []
    compliance: list[AdminComplianceOut] = []
    notes: list[SupportNoteOut] = []


class ProjectActionRequest(BaseModel):
    """POST /admin/projects/{id}/actions (PRD §9.5)."""
    action: str
    reason: Optional[str] = None
    hours: Optional[int] = Field(default=None, ge=1, le=8760)  # extend_retention only

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in PROJECT_ACTIONS:
            raise ValueError(f"action must be one of {', '.join(PROJECT_ACTIONS)}")
        return v

    @model_validator(mode="after")
    def _hours_required(self) -> "ProjectActionRequest":
        if self.action == "extend_retention" and self.hours is None:
            raise ValueError("'extend_retention' requires 'hours'")
        if self.action in ("expire_now", "delete_files") and not (self.reason or "").strip():
            raise ValueError(f"'{self.action}' requires a reason")
        return self


class ProjectActionResponse(BaseModel):
    id: str
    status: str
    locked: bool
    expires_at: Optional[datetime] = None


# --- Admin Panel Phase 4: billing / payments / subscriptions / plans /
#     promos / credits (PRD §13–17). Sensitive gateway IDs are masked in the
#     route layer (PRD §13.4, §33.2) before these models are populated. ---


class BillingOverviewOut(BaseModel):
    """GET /admin/billing — dashboard cards (PRD §13.1). Amounts in paise."""
    revenue_today_inr: int
    revenue_month_inr: int
    mrr_inr: int
    active_subscriptions: int
    new_subscriptions: int
    renewals: int
    cancellations: int
    failed_payments: int
    refunds_inr: int
    arpu_inr: int


class PaymentListItem(BaseModel):
    """Row in GET /admin/payments (PRD §13.3). razorpay_payment_id is masked."""
    id: str
    user_id: str
    user_email: Optional[str] = None
    plan_id: Optional[str] = None
    amount_inr: int
    currency: str
    status: str
    method: Optional[str] = None
    razorpay_payment_id: Optional[str] = None  # masked
    promo_code: Optional[str] = None
    refund_status: Optional[str] = None
    refunded_inr: int = 0
    manual_review: bool = False
    created_at: datetime


class PaymentPage(PageMeta):
    items: list[PaymentListItem]


class RefundOut(BaseModel):
    id: str
    payment_id: str
    user_id: str
    amount_inr: int
    kind: str
    reason: Optional[str] = None
    razorpay_refund_id: Optional[str] = None  # masked
    status: str
    admin_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentDetailOut(BaseModel):
    """GET /admin/payments/{id} (PRD §13.2). Gateway IDs masked in the route."""
    id: str
    user_id: str
    user_email: Optional[str] = None
    subscription_id: Optional[str] = None
    plan_id: Optional[str] = None
    amount_inr: int
    currency: str
    status: str
    method: Optional[str] = None
    description: Optional[str] = None
    discount_inr: int = 0
    tax_inr: int = 0
    credits_issued: int = 0
    promo_code: Optional[str] = None
    razorpay_payment_id: Optional[str] = None  # masked
    razorpay_order_id: Optional[str] = None  # masked
    razorpay_subscription_id: Optional[str] = None  # masked
    captured_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    refund_status: Optional[str] = None
    refunded_inr: int = 0
    refundable_inr: int = 0
    manual_review: bool = False
    internal_note: Optional[str] = None
    created_at: datetime
    refunds: list[RefundOut] = []


class RefundRequest(BaseModel):
    """POST /admin/payments/{id}/refund (PRD §13.5). Reason mandatory; refunds
    at/above the threshold require a super-admin actor (enforced in route)."""
    amount_inr: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=2000)


class PaymentNoteRequest(BaseModel):
    """POST /admin/payments/{id}/note — internal note + manual-review toggle."""
    internal_note: Optional[str] = Field(default=None, max_length=8000)
    manual_review: Optional[bool] = None


class WebhookEventOut(BaseModel):
    id: str
    event_type: str
    razorpay_event_id: Optional[str] = None  # masked
    payment_id: Optional[str] = None
    subscription_ref: Optional[str] = None
    signature_valid: bool
    status: str
    result: Optional[str] = None
    created_at: datetime
    payload: Optional[dict] = None  # only on detail; masked

    model_config = {"from_attributes": True}


class WebhookEventPage(PageMeta):
    items: list[WebhookEventOut]


class AdminSubscriptionListItem(BaseModel):
    """Row in GET /admin/subscriptions (PRD §14.1)."""
    id: str
    user_id: str
    user_email: Optional[str] = None
    plan_id: str
    status: str
    display_status: str
    cancel_at_period_end: bool = False
    payment_failures: int = 0
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    grace_until: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime


class AdminSubscriptionPage(PageMeta):
    items: list[AdminSubscriptionListItem]


SUBSCRIPTION_ACTIONS = ("cancel", "cancel_at_period_end", "resume", "reactivate", "change_plan")


class SubscriptionActionRequest(BaseModel):
    """POST /admin/subscriptions/{id}/actions (PRD §14.4)."""
    action: str
    reason: Optional[str] = None
    plan_id: Optional[str] = None  # change_plan only

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in SUBSCRIPTION_ACTIONS:
            raise ValueError(f"action must be one of {', '.join(SUBSCRIPTION_ACTIONS)}")
        return v

    @model_validator(mode="after")
    def _validate(self) -> "SubscriptionActionRequest":
        if self.action == "change_plan" and not (self.plan_id or "").strip():
            raise ValueError("'change_plan' requires plan_id")
        if self.action == "cancel" and not (self.reason or "").strip():
            raise ValueError("'cancel' requires a reason")
        return self


class PlanOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    price_inr: int
    annual_price_inr: Optional[int] = None
    currency: str = "INR"
    billing_interval: str = "monthly"
    credits_per_day: int
    monthly_credits: Optional[int] = None
    razorpay_plan_id: Optional[str] = None
    is_active: bool = True
    archived: bool = False
    is_recommended: bool = False
    display_order: int = 0
    max_upload_mb: Optional[int] = None
    max_duration_seconds: Optional[int] = None
    max_resolution: Optional[str] = None
    concurrent_jobs: Optional[int] = None
    storage_allowance_mb: Optional[int] = None
    retention_days: Optional[int] = None
    priority_level: int = 0
    api_access: bool = False
    support_level: Optional[str] = None
    subscriber_count: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PlanCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    description: Optional[str] = None
    price_inr: int = Field(ge=0)
    annual_price_inr: Optional[int] = Field(default=None, ge=0)
    currency: str = "INR"
    billing_interval: str = "monthly"
    credits_per_day: int = Field(ge=0)
    monthly_credits: Optional[int] = Field(default=None, ge=0)
    razorpay_plan_id: Optional[str] = None
    is_recommended: bool = False
    display_order: int = 0
    max_upload_mb: Optional[int] = Field(default=None, ge=0)
    max_duration_seconds: Optional[int] = Field(default=None, ge=0)
    max_resolution: Optional[str] = None
    concurrent_jobs: Optional[int] = Field(default=None, ge=0)
    storage_allowance_mb: Optional[int] = Field(default=None, ge=0)
    retention_days: Optional[int] = Field(default=None, ge=0)
    priority_level: int = 0
    api_access: bool = False
    support_level: Optional[str] = None


class PlanUpdateRequest(BaseModel):
    """Partial update for PATCH /admin/plans/{id} (PRD §15.2)."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    description: Optional[str] = None
    price_inr: Optional[int] = Field(default=None, ge=0)
    annual_price_inr: Optional[int] = Field(default=None, ge=0)
    currency: Optional[str] = None
    billing_interval: Optional[str] = None
    credits_per_day: Optional[int] = Field(default=None, ge=0)
    monthly_credits: Optional[int] = Field(default=None, ge=0)
    razorpay_plan_id: Optional[str] = None
    is_active: Optional[bool] = None
    archived: Optional[bool] = None
    is_recommended: Optional[bool] = None
    display_order: Optional[int] = None
    max_upload_mb: Optional[int] = Field(default=None, ge=0)
    max_duration_seconds: Optional[int] = Field(default=None, ge=0)
    max_resolution: Optional[str] = None
    concurrent_jobs: Optional[int] = Field(default=None, ge=0)
    storage_allowance_mb: Optional[int] = Field(default=None, ge=0)
    retention_days: Optional[int] = Field(default=None, ge=0)
    priority_level: Optional[int] = None
    api_access: Optional[bool] = None
    support_level: Optional[str] = None
    reason: Optional[str] = None


class PromoOut(BaseModel):
    id: str
    code: str
    description: Optional[str] = None
    discount_type: str = "percentage"
    discount_value: Optional[int] = None
    discount_percent: int = 0
    max_discount_inr: Optional[int] = None
    applicable_plans: Optional[list] = None
    is_active: bool = True
    sandbox_only: bool = False
    new_users_only: bool = False
    min_purchase_inr: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    max_total_uses: Optional[int] = None
    max_uses_per_user: Optional[int] = None
    times_redeemed: int = 0
    remaining_uses: Optional[int] = None
    razorpay_offer_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PromoCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    description: Optional[str] = None
    discount_type: str = "percentage"
    discount_value: int = Field(ge=0)
    max_discount_inr: Optional[int] = Field(default=None, ge=0)
    applicable_plans: Optional[list[str]] = None
    sandbox_only: bool = False
    new_users_only: bool = False
    min_purchase_inr: Optional[int] = Field(default=None, ge=0)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    max_total_uses: Optional[int] = Field(default=None, ge=0)
    max_uses_per_user: Optional[int] = Field(default=None, ge=0)
    razorpay_offer_id: Optional[str] = None


class PromoUpdateRequest(BaseModel):
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[int] = Field(default=None, ge=0)
    max_discount_inr: Optional[int] = Field(default=None, ge=0)
    applicable_plans: Optional[list[str]] = None
    is_active: Optional[bool] = None
    sandbox_only: Optional[bool] = None
    new_users_only: Optional[bool] = None
    min_purchase_inr: Optional[int] = Field(default=None, ge=0)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    max_total_uses: Optional[int] = Field(default=None, ge=0)
    max_uses_per_user: Optional[int] = Field(default=None, ge=0)
    razorpay_offer_id: Optional[str] = None
    reason: Optional[str] = None


class CreditDashboardOut(BaseModel):
    """GET /admin/credits (PRD §17.1)."""
    credits_issued_today: int
    credits_consumed_today: int
    credits_refunded_today: int
    bonus_credits_today: int
    low_balance_users: list[AdminUser] = []


# --- Admin Panel Phase 5: storage & compliance (PRD §18, §21). Raw storage
#     keys/paths are only surfaced to roles that pass projects.manage; the route
#     layer masks them otherwise (PRD §21.4/§21.6). ---


STORAGE_ACTIONS = (
    "extend_retention",
    "expire_now",
    "trigger_cleanup",
    "retry_cleanup",
    "lock_compliance",
    "verify_existence",
)

COMPLIANCE_ACTIONS = (
    "mark_safe",
    "request_information",
    "restrict_processing",
    "disable_downloads",
    "suspend_account",
    "ban_account",
    "place_legal_hold",
    "remove_legal_hold",
    "escalate",
    "add_note",
    "close",
)

ABUSE_SEVERITIES = ("low", "medium", "high", "critical")


class StorageOverviewOut(BaseModel):
    """GET /admin/storage (PRD §18.1). Byte totals per bucket + estimated spend."""
    total_bytes: int
    buckets: dict[str, int]
    estimated_cost_inr: int  # paise, ₹2.00/GB-month estimate
    key_counts: dict[str, int] = {}


class RetentionItem(BaseModel):
    """One output file row in the §18.3 retention dashboard."""
    output_id: str
    project_id: str
    project_title: Optional[str] = None
    bucket: str
    storage_key: str
    file_size: Optional[int] = None
    expires_at: Optional[datetime] = None
    legal_hold: bool = False
    retention_extended: bool = False
    cleanup_failed: bool = False
    retention_state: str  # locked | failed_cleanup | past_retention | ...


class RetentionPage(PageMeta):
    items: list[RetentionItem] = []


class StorageActionRequest(BaseModel):
    """POST /admin/projects/{id}/storage (PRD §18.4). Destructive actions
    require a reason; extend_retention requires hours."""
    action: str
    reason: Optional[str] = None
    hours: Optional[int] = Field(default=None, ge=1, le=8760)

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in STORAGE_ACTIONS:
            raise ValueError(f"action must be one of {', '.join(STORAGE_ACTIONS)}")
        return v

    @model_validator(mode="after")
    def _guards(self) -> "StorageActionRequest":
        if self.action == "extend_retention" and self.hours is None:
            raise ValueError("'extend_retention' requires 'hours'")
        if self.action in ("trigger_cleanup", "retry_cleanup", "expire_now", "lock_compliance") \
                and not (self.reason or "").strip():
            raise ValueError(f"'{self.action}' requires a reason")
        return self


class StorageActionResponse(BaseModel):
    id: str
    action: str
    expires_at: Optional[datetime] = None
    locked: bool = False
    result: dict = {}


class ComplianceOverviewOut(BaseModel):
    """GET /admin/compliance (PRD §21.1)."""
    ownership_confirmations: int
    projects_reported: int
    open_reviews: int
    suspended_accounts: int
    repeat_offenders: int
    high_risk_uploads: int
    missing_confirmations: int
    projects_on_legal_hold: int


class AbuseReportDetail(BaseModel):
    """GET /admin/compliance/{id} — a report + its project/reporter context
    (PRD §21.4). Storage keys are only populated for privileged roles."""
    id: str
    project_id: Optional[str] = None
    project_title: Optional[str] = None
    project_owner_email: Optional[str] = None
    reported_by: Optional[str] = None
    reporter_email: Optional[str] = None
    reason: str
    status: str
    severity: str = "medium"
    assigned_reviewer: Optional[str] = None
    resolution_note: Optional[str] = None
    legal_hold: bool = False
    legal_hold_reason: Optional[str] = None
    processing_restricted: bool = False
    downloads_disabled: bool = False
    previous_reports: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None


class AbuseReportPage(PageMeta):
    items: list[AbuseReportSummary] = []


class ComplianceActionRequest(BaseModel):
    """POST /admin/compliance/{id}/actions (PRD §21.5)."""
    action: str
    reason: Optional[str] = None

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in COMPLIANCE_ACTIONS:
            raise ValueError(f"action must be one of {', '.join(COMPLIANCE_ACTIONS)}")
        return v


class ComplianceActionResponse(BaseModel):
    id: str
    status: str
    account_status: Optional[str] = None


class AbuseSeverityRequest(BaseModel):
    """PATCH /admin/compliance/{id} — triage fields (PRD §21.2)."""
    severity: str

    @field_validator("severity")
    @classmethod
    def _check(cls, v: str) -> str:
        if v.strip().lower() not in ABUSE_SEVERITIES:
            raise ValueError(f"severity must be one of {', '.join(ABUSE_SEVERITIES)}")
        return v.strip().lower()


# --- Phase 6: models, presets, feature flags, notifications, maintenance ---

MODEL_TYPES = (
    "watermark_detection", "ocr_detection", "segmentation", "static_tracking",
    "moving_tracking", "image_inpainting", "temporal_video_inpainting",
    "artifact_detection", "quality_validation",
)
MODEL_ACTIONS = (
    "enable_testing", "enable_production", "disable", "set_default",
    "set_fallback", "rollback", "deprecate",
)
ROLLOUT_STRATEGIES = ("internal", "selected_users", "percentage", "plans", "full")
BROADCAST_KINDS = ("in_app", "maintenance", "feature", "billing", "policy")
BROADCAST_TARGETS = (
    "all", "specific_plan", "active_subscribers", "free_users",
    "selected_users", "users_with_active_jobs",
)


class AIModelOut(BaseModel):
    """GET /admin/models item (PRD §19)."""
    id: str
    name: str
    model_type: str
    version: str
    status: str
    is_default: bool = False
    is_fallback: bool = False
    deployment_date: Optional[datetime] = None
    supported_job_types: Optional[list] = None
    supported_resolutions: Optional[list] = None
    min_gpu_memory_mb: Optional[int] = None
    avg_speed_fps: Optional[float] = None
    failure_rate: Optional[float] = None
    quality_score: Optional[float] = None
    rollout_strategy: str = "internal"
    rollout_percentage: int = 0
    rollout_plans: Optional[list] = None
    compatible_workers: Optional[list] = None
    previous_version: Optional[str] = None
    release_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class AIModelCreate(BaseModel):
    """POST /admin/models (PRD §19.1). Registers a new model version."""
    name: str = Field(min_length=1, max_length=128)
    model_type: str
    version: str = Field(min_length=1, max_length=64)
    supported_job_types: Optional[list] = None
    supported_resolutions: Optional[list] = None
    min_gpu_memory_mb: Optional[int] = Field(default=None, ge=0)
    avg_speed_fps: Optional[float] = Field(default=None, ge=0)
    quality_score: Optional[float] = Field(default=None, ge=0, le=100)
    compatible_workers: Optional[list] = None
    previous_version: Optional[str] = None
    release_notes: Optional[str] = None

    model_config = {"protected_namespaces": ()}

    @field_validator("model_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v.strip().lower() not in MODEL_TYPES:
            raise ValueError(f"model_type must be one of {', '.join(MODEL_TYPES)}")
        return v.strip().lower()


class AIModelUpdate(BaseModel):
    """PATCH /admin/models/{id} — metadata + staged rollout (PRD §19.5)."""
    release_notes: Optional[str] = None
    supported_job_types: Optional[list] = None
    supported_resolutions: Optional[list] = None
    compatible_workers: Optional[list] = None
    rollout_strategy: Optional[str] = None
    rollout_percentage: Optional[int] = Field(default=None, ge=0, le=100)
    rollout_plans: Optional[list] = None

    @field_validator("rollout_strategy")
    @classmethod
    def _check_strategy(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip().lower() not in ROLLOUT_STRATEGIES:
            raise ValueError(f"rollout_strategy must be one of {', '.join(ROLLOUT_STRATEGIES)}")
        return v.strip().lower() if v is not None else v


class ModelActionRequest(BaseModel):
    """POST /admin/models/{id}/actions (PRD §19.4)."""
    action: str
    reason: Optional[str] = None

    @field_validator("action")
    @classmethod
    def _check(cls, v: str) -> str:
        if v not in MODEL_ACTIONS:
            raise ValueError(f"action must be one of {', '.join(MODEL_ACTIONS)}")
        return v


class PresetOut(BaseModel):
    """GET /admin/presets item (PRD §20)."""
    id: str
    name: str
    description: Optional[str] = None
    enabled: bool = True
    is_default: bool = False
    required_plan: Optional[str] = None
    detection_model: Optional[str] = None
    tracking_model: Optional[str] = None
    inpainting_model: Optional[str] = None
    output_resolution: Optional[str] = None
    frame_sampling_rate: Optional[int] = None
    temporal_window: Optional[int] = None
    mask_expansion: int = 0
    feathering: int = 4
    temporal_smoothing: bool = False
    encoding_codec: str = "libx264"
    encoding_quality: Optional[int] = None
    expected_credit_cost: Optional[int] = None
    max_duration_seconds: Optional[int] = None
    worker_requirements: Optional[dict] = None
    estimated_relative_speed: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PresetWrite(BaseModel):
    """POST /admin/presets and PATCH body (PRD §20.2). All params optional on
    PATCH; ``name`` required on create (enforced in the route)."""
    name: Optional[str] = Field(default=None, max_length=128)
    description: Optional[str] = None
    enabled: Optional[bool] = None
    required_plan: Optional[str] = None
    detection_model: Optional[str] = None
    tracking_model: Optional[str] = None
    inpainting_model: Optional[str] = None
    output_resolution: Optional[str] = None
    frame_sampling_rate: Optional[int] = Field(default=None, ge=1)
    temporal_window: Optional[int] = Field(default=None, ge=0)
    mask_expansion: Optional[int] = Field(default=None, ge=0)
    feathering: Optional[int] = Field(default=None, ge=0)
    temporal_smoothing: Optional[bool] = None
    encoding_codec: Optional[str] = None
    encoding_quality: Optional[int] = Field(default=None, ge=0, le=100)
    expected_credit_cost: Optional[int] = Field(default=None, ge=0)
    max_duration_seconds: Optional[int] = Field(default=None, ge=0)
    estimated_relative_speed: Optional[float] = Field(default=None, ge=0)


class FeatureFlagOut(BaseModel):
    """A single feature flag (PRD §26.5)."""
    key: str
    label: str
    enabled: bool
    description: Optional[str] = None


class FeatureFlagUpdate(BaseModel):
    """PATCH /admin/feature-flags/{key}."""
    enabled: bool


class NotificationTemplateOut(BaseModel):
    """GET /admin/notifications/templates item (PRD §23.1)."""
    id: str
    key: str
    name: str
    subject: str
    html_content: str = ""
    text_content: str = ""
    variables: Optional[list] = None
    enabled: bool = True
    version: int = 1
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NotificationTemplateUpdate(BaseModel):
    """PATCH /admin/notifications/templates/{id} (PRD §23.2)."""
    subject: Optional[str] = Field(default=None, max_length=255)
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    variables: Optional[list] = None
    enabled: Optional[bool] = None


class TemplatePreviewRequest(BaseModel):
    """POST /admin/notifications/templates/{id}/preview — sample variable fill."""
    variables: dict = {}


class TemplatePreviewResponse(BaseModel):
    subject: str
    html_content: str
    text_content: str


class BroadcastRequest(BaseModel):
    """POST /admin/notifications/broadcast (PRD §23.3)."""
    kind: str
    title: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1)
    target: str = "all"
    target_plan: Optional[str] = None

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, v: str) -> str:
        if v not in BROADCAST_KINDS:
            raise ValueError(f"kind must be one of {', '.join(BROADCAST_KINDS)}")
        return v

    @field_validator("target")
    @classmethod
    def _check_target(cls, v: str) -> str:
        if v not in BROADCAST_TARGETS:
            raise ValueError(f"target must be one of {', '.join(BROADCAST_TARGETS)}")
        return v


class BroadcastResponse(BaseModel):
    id: str
    kind: str
    target: str
    recipient_count: int


class MaintenanceState(BaseModel):
    """GET/PUT /admin/maintenance (PRD §26.6)."""
    maintenance_enabled: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    public_message: str = ""
    allow_administrators: bool = True
    allow_existing_jobs_to_finish: bool = True
    pause_new_uploads: bool = True
    pause_new_processing_jobs: bool = True
    disable_checkout: bool = False
    status_page_link: Optional[str] = None

    @field_validator("status_page_link")
    @classmethod
    def _validate_status_page_link(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        candidate = value.strip()
        if not candidate:
            return None
        parsed = urlparse(candidate)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("status_page_link must be an absolute http(s) URL")
        return candidate

    @model_validator(mode="after")
    def _validate_window(self) -> "MaintenanceState":
        """A scheduled window cannot end before it starts."""
        if self.start_time and self.end_time:
            start = self.start_time if self.start_time.tzinfo else self.start_time.replace(tzinfo=timezone.utc)
            end = self.end_time if self.end_time.tzinfo else self.end_time.replace(tzinfo=timezone.utc)
            if end <= start:
                raise ValueError("end_time must be later than start_time")
        return self


# =====================================================================
# Phase 7 — analytics / exports / system health / admin-mgmt / search / secrets
# =====================================================================

INCIDENT_ACTIONS = ("acknowledge", "silence", "add_note", "resolve", "reopen")
ADMIN_MGMT_ACTIONS = (
    "assign_role", "change_role", "suspend", "reactivate",
    "revoke_sessions", "require_password_reset", "require_mfa", "remove",
)
EXPORT_FORMATS = ("csv", "json")


class AnalyticsOut(BaseModel):
    """GET /admin/analytics (PRD §24). Rates are floats in [0,1]; cost fields are
    paise ints. Sub-dicts are permissive (Optional) so a partial snapshot still
    serializes."""
    product: dict = Field(default_factory=dict)
    processing: dict = Field(default_factory=dict)
    business: dict = Field(default_factory=dict)
    cost: dict = Field(default_factory=dict)
    window_days: Optional[int] = None


class ExportRequest(BaseModel):
    """POST /admin/exports (PRD §24.5)."""
    dataset: str  # users | payments | jobs | audit
    format: str = "csv"

    @field_validator("format")
    @classmethod
    def _check_format(cls, v: str) -> str:
        v = (v or "csv").lower()
        if v not in EXPORT_FORMATS:
            raise ValueError(f"format must be one of {', '.join(EXPORT_FORMATS)}")
        return v

    @field_validator("dataset")
    @classmethod
    def _check_dataset(cls, v: str) -> str:
        allowed = ("users", "payments", "jobs", "audit")
        if v not in allowed:
            raise ValueError(f"dataset must be one of {', '.join(allowed)}")
        return v


class ServiceStatusOut(BaseModel):
    name: str
    status: str  # operational | down | unknown
    detail: Optional[str] = None
    latency_ms: Optional[float] = None


class HealthMetricOut(BaseModel):
    metric: str
    value: Optional[float] = None
    status: str  # ok | warn | critical | unknown
    unit: Optional[str] = None


class SystemHealthOut(BaseModel):
    """GET /admin/system-health (PRD §25.1/§25.2)."""
    overall: str
    services: list[ServiceStatusOut] = Field(default_factory=list)
    metrics: list[HealthMetricOut] = Field(default_factory=list)
    checked_at: datetime


class IncidentOut(BaseModel):
    id: str
    service: str
    severity: str
    status: str
    title: str
    detail: Optional[str] = None
    notes: Optional[list] = None
    silenced_until: Optional[datetime] = None
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class IncidentCreate(BaseModel):
    service: str
    title: str = Field(min_length=1, max_length=255)
    severity: str = "minor"
    detail: Optional[str] = None

    @field_validator("severity")
    @classmethod
    def _check_sev(cls, v: str) -> str:
        allowed = ("info", "minor", "major", "critical")
        if v not in allowed:
            raise ValueError(f"severity must be one of {', '.join(allowed)}")
        return v


class IncidentActionRequest(BaseModel):
    action: str
    note: Optional[str] = None
    minutes: Optional[int] = Field(default=None, ge=1, le=1440)  # silence window

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in INCIDENT_ACTIONS:
            raise ValueError(f"action must be one of {', '.join(INCIDENT_ACTIONS)}")
        return v


class AdminListItem(BaseModel):
    """§28.1 administrator list row."""
    id: str
    email: str
    full_name: str
    admin_role: Optional[str] = None
    account_status: str
    mfa_enabled: bool = False
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    admin_created_by: Optional[str] = None


class AdminMgmtActionRequest(BaseModel):
    """POST /admin/administrators/{id}/actions (PRD §28.2)."""
    action: str
    new_role: Optional[str] = None
    reason: Optional[str] = None

    @field_validator("action")
    @classmethod
    def _check_action(cls, v: str) -> str:
        if v not in ADMIN_MGMT_ACTIONS:
            raise ValueError(f"action must be one of {', '.join(ADMIN_MGMT_ACTIONS)}")
        return v


class AdminInviteRequest(BaseModel):
    """POST /admin/administrators (PRD §28.2 invite)."""
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    admin_role: str

    @field_validator("email")
    @classmethod
    def _check_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("email must be a valid address")
        return v.lower()


class SearchResultItem(BaseModel):
    id: str
    label: str
    sublabel: Optional[str] = None


class SearchGroupOut(BaseModel):
    entity_type: str
    items: list[SearchResultItem] = Field(default_factory=list)


class GlobalSearchOut(BaseModel):
    """GET /admin/search?q= (PRD §29)."""
    query: str
    groups: list[SearchGroupOut] = Field(default_factory=list)


class SecretDescriptorOut(BaseModel):
    """§26.7 — non-revealing secret descriptor. Never carries a private value."""
    name: str
    configured: bool
    public: bool = False
    value: Optional[str] = None  # only ever populated for public identifiers
    last_four: str = ""
    updated_at: Optional[str] = None


class SecretsOut(BaseModel):
    secrets: list[SecretDescriptorOut] = Field(default_factory=list)


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
    # Phase 3
    "JobStageStep",
    "AdminJobDetail",
    "QueueInfo",
    "QueueMetrics",
    "WorkerDetail",
    # Phases 1+2
    "AdminMe",
    "PageMeta",
    "AdminUserPage",
    "AuditPage",
    "AdminUserActionRequest",
    "RoleChangeRequest",
    "PlanChangeRequest",
    "CreditAdjustRequest",
    "CreditTransactionOut",
    "CreditTxnPage",
    "PaymentOut",
    "SupportNoteOut",
    "SupportNoteCreate",
    "AdminSubscriptionOut",
    "AdminSessionOut",
    "AdminUserDetail",
    "AdminProject",
    "AdminProjectPage",
    "AdminOutputFileOut",
    "AdminComplianceOut",
    "AdminProjectDetail",
    "ProjectActionRequest",
    "ProjectActionResponse",
    # Phase 4 — billing / payments / subscriptions / plans / promos / credits
    "BillingOverviewOut",
    "PaymentListItem",
    "PaymentPage",
    "PaymentDetailOut",
    "RefundOut",
    "RefundRequest",
    "PaymentNoteRequest",
    "WebhookEventOut",
    "WebhookEventPage",
    "AdminSubscriptionListItem",
    "AdminSubscriptionPage",
    "SubscriptionActionRequest",
    "SUBSCRIPTION_ACTIONS",
    "PlanOut",
    "PlanCreateRequest",
    "PlanUpdateRequest",
    "PromoOut",
    "PromoCreateRequest",
    "PromoUpdateRequest",
    "CreditDashboardOut",
    # Phase 5 — storage & compliance
    "StorageOverviewOut",
    "RetentionItem",
    "RetentionPage",
    "StorageActionRequest",
    "StorageActionResponse",
    "STORAGE_ACTIONS",
    "ComplianceOverviewOut",
    "AbuseReportDetail",
    "AbuseReportPage",
    "ComplianceActionRequest",
    "ComplianceActionResponse",
    "AbuseSeverityRequest",
    "COMPLIANCE_ACTIONS",
    "ABUSE_SEVERITIES",
    "ALL_USER_ACTIONS",
    "USER_SUPPORT_ACTIONS",
    "USER_MANAGE_ACTIONS",
    "USER_DELETE_ACTIONS",
    "PROJECT_ACTIONS",
    "DESTRUCTIVE_USER_ACTIONS",
    # Phase 6 — models / presets / feature flags / notifications / maintenance
    "AIModelOut",
    "AIModelCreate",
    "AIModelUpdate",
    "ModelActionRequest",
    "PresetOut",
    "PresetWrite",
    "FeatureFlagOut",
    "FeatureFlagUpdate",
    "NotificationTemplateOut",
    "NotificationTemplateUpdate",
    "TemplatePreviewRequest",
    "TemplatePreviewResponse",
    "BroadcastRequest",
    "BroadcastResponse",
    "MaintenanceState",
    "MODEL_TYPES",
    "MODEL_ACTIONS",
    "ROLLOUT_STRATEGIES",
    "BROADCAST_KINDS",
    "BROADCAST_TARGETS",
    # Phase 7 — analytics / exports / health / admin-mgmt / search / secrets
    "AnalyticsOut",
    "ExportRequest",
    "ServiceStatusOut",
    "HealthMetricOut",
    "SystemHealthOut",
    "IncidentOut",
    "IncidentCreate",
    "IncidentActionRequest",
    "AdminListItem",
    "AdminMgmtActionRequest",
    "AdminInviteRequest",
    "SearchResultItem",
    "SearchGroupOut",
    "GlobalSearchOut",
    "SecretDescriptorOut",
    "SecretsOut",
    "INCIDENT_ACTIONS",
    "ADMIN_MGMT_ACTIONS",
    "EXPORT_FORMATS",
]
