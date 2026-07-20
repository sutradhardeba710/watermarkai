"""Admin service (SRS ADMIN-001..007, MON, STORAGE-006, RECON-008).

Two kinds of code live here:

* **Pure helpers** (no DB / no SQLAlchemy import) — config serialization,
  retention policy, audit-detail shapes, worker-online decision. These run
  on the 32-bit dev box and are unit-tested directly.
* **Orchestration helpers** that take a ``Session`` and compose the
  repository layer + the pure helpers — used by the route layer at runtime.

The split mirrors the rest of the codebase (see ``job_states.py`` /
``mask_morph.py``): keep the testable policy out of the ORM path.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional

from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.admin import SystemConfig, WorkerInfo
from app.services.admin_permissions import PERMISSIONS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import AccountStatus, JobState, JobType, ProcessingJob, User
    from app.repositories import admin as admin_repo
    from app.repositories import processing as proc_repo


# --- ADMIN-005: config (de)serialization (pure) ---


# Keys that are persisted as JSON arrays in SystemSetting.value.
_LIST_KEYS = {
    "allowed_upload_extensions",
    "enabled_models",
}
# Keys persisted as plain ints.
_INT_KEYS = {
    "max_file_size_mb", "max_duration_seconds", "max_width", "max_height", "max_fps",
    "retain_original_hours", "retain_preview_hours", "retain_output_days",
    "retain_failed_hours", "worker_concurrency", "max_retries",
}
# The single bool knob.
_BOOL_KEYS = {"maintenance_mode"}

# All knobs an admin can override. Mirrors SystemConfig fields.
ALL_CONFIG_KEYS = _LIST_KEYS | _INT_KEYS | _BOOL_KEYS

# A worker is offline if its heartbeat is older than this (SRS ADMIN-004 +
# MON-002). Kept here as a module constant so the pure is_worker_online path
# doesn't import the repo layer (which pulls SQLAlchemy). admin_repo re-exports
# the same value via worker_offline_threshold_seconds().
WORKER_OFFLINE_THRESHOLD_SECONDS = 90


def config_value_to_str(key: str, value: Any) -> str:
    """Serialize a config value for storage in SystemSetting.value (Text)."""
    if key in _LIST_KEYS:
        return json.dumps([str(v) for v in value])
    if key in _BOOL_KEYS:
        return "true" if value else "false"
    return str(value)


def config_value_from_str(key: str, raw: str) -> Any:
    """Deserialize a stored config value back to its Python type."""
    if key in _LIST_KEYS:
        try:
            return list(json.loads(raw)) if raw else []
        except (ValueError, TypeError):
            return []
    if key in _BOOL_KEYS:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if key in _INT_KEYS:
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 0
    return raw


def build_config(settings: "get_settings().__class__", overrides: Mapping[str, str]) -> SystemConfig:
    """Merge the base Settings with any persisted overrides into a SystemConfig.

    Pure — takes the already-loaded settings + the override dict so it can be
    unit-tested with a stub settings object.
    """
    def get(key: str, default: Any) -> Any:
        if key in overrides:
            return config_value_from_str(key, overrides[key])
        return getattr(settings, key, default)

    return SystemConfig(
        max_file_size_mb=get("max_file_size_mb", 500),
        max_duration_seconds=get("max_duration_seconds", 300),
        max_width=get("max_width", 1920),
        max_height=get("max_height", 1080),
        max_fps=get("max_fps", 60),
        allowed_upload_extensions=get("allowed_upload_extensions", ["mp4", "mov", "webm"]),
        retain_original_hours=get("retain_original_hours", 24),
        retain_preview_hours=get("retain_preview_hours", 24),
        retain_output_days=get("retain_output_days", 7),
        retain_failed_hours=get("retain_failed_hours", 6),
        worker_concurrency=get("worker_concurrency", 2),
        max_retries=get("max_retries", 2),
        enabled_models=get("enabled_models", ["yolo", "easyocr"]),
        maintenance_mode=get("maintenance_mode", False),
    )


# --- ADMIN-004: worker online decision (pure) ---


def is_worker_online(last_heartbeat: Optional[datetime], now: Optional[datetime] = None) -> bool:
    """A worker is online if its heartbeat is within the offline threshold.

    ``now`` is injectable so unit tests don't depend on wall-clock time. The
    threshold is the module constant ``WORKER_OFFLINE_THRESHOLD_SECONDS``,
    re-exported by ``admin_repo.worker_offline_threshold_seconds()``.
    """
    if last_heartbeat is None:
        return False
    ref = now or datetime.now(timezone.utc)
    hb = last_heartbeat
    if hb.tzinfo is None:
        hb = hb.replace(tzinfo=timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    age = (ref - hb).total_seconds()
    return age <= WORKER_OFFLINE_THRESHOLD_SECONDS


def fuse_workers(
    nodes: Iterable,
    heartbeats: Mapping[str, int],
    now: Optional[datetime] = None,
) -> list[WorkerInfo]:
    """Fuse the worker_nodes table with the Redis heartbeat hash (epoch seconds).

    Pure — both inputs are plain data so the fusion is unit-testable. ``nodes``
    are ORM WorkerNode rows (or any objects exposing the named attributes);
    ``heartbeats`` maps worker name → epoch-seconds int.
    """
    out: list[WorkerInfo] = []
    for n in nodes:
        hb_epoch = heartbeats.get(n.name)
        last_hb: Optional[datetime] = n.last_heartbeat
        if hb_epoch is not None and (last_hb is None or _heartbeat_newer(hb_epoch, last_hb)):
            last_hb = datetime.fromtimestamp(int(hb_epoch), tz=timezone.utc)
        online = is_worker_online(last_hb, now=now)
        out.append(WorkerInfo(
            name=n.name,
            online=online,
            status=n.status,
            gpu_name=n.gpu_name,
            gpu_memory=n.gpu_memory,
            active_job_id=n.active_job_id,
            last_heartbeat=last_hb,
            software_version=n.software_version,
        ))
    return out


def _heartbeat_newer(epoch: int, last_hb: datetime) -> bool:
    hb = last_hb.replace(tzinfo=timezone.utc) if last_hb.tzinfo is None else last_hb
    return epoch > hb.timestamp()


# --- ADMIN-006: audit detail shapes (pure) ---


def audit_details(action: str, **fields: Any) -> dict[str, Any]:
    """Build a consistent details payload for an audit row. Drops None values
    so the JSON column stays compact."""
    return {k: v for k, v in fields.items() if v is not None}


# --- Admin Panel Phases 1+2: pagination / credits / action guards (pure) ---


DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100


def paginate(page: Any, page_size: Any, *, max_page_size: int = MAX_PAGE_SIZE) -> tuple[int, int, int, int]:
    """Clamp page/page_size and return ``(page, page_size, limit, offset)``.

    Tolerates None / junk input (falls back to defaults) so route query params
    can be passed straight through.
    """
    try:
        p = max(1, int(page))
    except (TypeError, ValueError):
        p = 1
    try:
        ps = int(page_size)
    except (TypeError, ValueError):
        ps = DEFAULT_PAGE_SIZE
    ps = min(max(1, ps), max_page_size)
    return p, ps, ps, (p - 1) * ps


def page_envelope(items: list, total: int, page: int, page_size: int) -> dict[str, Any]:
    """The standard list-response envelope: {items, total, page, page_size}."""
    return {"items": items, "total": total, "page": page, "page_size": page_size}


CREDIT_SOURCES = ("admin", "job", "refund", "subscription", "reset")


def build_credit_txn(
    *,
    user_id: str,
    balance_before: int,
    amount: int,
    direction: str,
    source: str,
    reason: Optional[str] = None,
    project_id: Optional[str] = None,
    job_id: Optional[str] = None,
    admin_id: Optional[str] = None,
) -> dict[str, Any]:
    """Validate and shape an immutable credit-ledger entry (PRD §17.2).

    Raises ValueError on a non-positive amount, unknown direction/source, or a
    debit that would overdraw the balance. Returns the column dict for
    ``admin_repo.insert_credit_txn`` including the computed ``balance_after``.
    """
    if amount <= 0:
        raise ValueError("amount must be positive")
    if direction not in ("credit", "debit"):
        raise ValueError("direction must be 'credit' or 'debit'")
    if source not in CREDIT_SOURCES:
        raise ValueError(f"source must be one of {', '.join(CREDIT_SOURCES)}")
    balance_after = balance_before + amount if direction == "credit" else balance_before - amount
    if balance_after < 0:
        raise ValueError("debit would overdraw the balance")
    return {
        "user_id": user_id,
        "amount": amount,
        "direction": direction,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "reason": reason,
        "source": source,
        "project_id": project_id,
        "job_id": job_id,
        "admin_id": admin_id,
    }


def validate_user_admin_action(
    *,
    action: str,
    actor_id: str,
    target_id: str,
    target_is_staff: bool,
    actor_is_super: bool,
) -> None:
    """Guard rails for user actions (PRD §8.4 / §33.5). Pure — raises
    ValueError with a human-readable message; the route maps it to 409.

    - No acting on yourself with a status-changing action.
    - Only super admins may act on other staff accounts.
    """
    status_changing = {"suspend", "ban", "restore", "delete_account", "revoke_sessions", "force_password_reset"}
    if actor_id == target_id and action in status_changing:
        raise ValueError("You cannot perform this action on your own account.")
    if target_is_staff and not actor_is_super:
        raise ValueError("Only a super administrator can act on staff accounts.")


def extend_retention_expiry(
    current_expires_at: Optional[datetime], hours: int, now: Optional[datetime] = None
) -> datetime:
    """New expiry when extending retention: max(now, current) + hours. Pure."""
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    base = ref
    if current_expires_at is not None:
        cur = current_expires_at
        if cur.tzinfo is None:
            cur = cur.replace(tzinfo=timezone.utc)
        base = max(ref, cur)
    return base + timedelta(hours=hours)


def overview_extras(counts: Mapping[str, Any]) -> dict[str, Any]:
    """Derive presentation metrics from raw counts (pure). Currently just the
    job success rate — guarded against div-by-zero."""
    completed = int(counts.get("jobs_completed_today") or 0)
    failed = int(counts.get("jobs_failed_today") or 0)
    total = completed + failed
    rate = (completed / total) if total else None
    return {"success_rate": rate}


# --- Admin Panel Phase 3: job timeline / queue shaping (pure) ---


# Canonical stage pipelines per job type (PRD §10.4). The timeline renders
# these in order and marks each step done/current/pending from the job's state.
_JOB_PIPELINES: dict[str, list[tuple[str, str]]] = {
    "analyze": [
        ("created", "Queued"),
        ("analyzing", "Detecting watermarks"),
        ("awaiting_review", "Awaiting review"),
        ("completed", "Complete"),
    ],
    "preview": [
        ("created", "Queued"),
        ("preview_queued", "Preview queued"),
        ("preview_processing", "Rendering preview"),
        ("preview_ready", "Preview ready"),
        ("completed", "Complete"),
    ],
    "process": [
        ("created", "Queued"),
        ("processing_queued", "Processing queued"),
        ("processing", "Inpainting frames"),
        ("encoding", "Encoding output"),
        ("completed", "Complete"),
    ],
}
# Fallback pipeline for job types without an explicit map (track/encode).
_DEFAULT_PIPELINE = [
    ("created", "Queued"),
    ("processing", "Running"),
    ("completed", "Complete"),
]

_TERMINAL_STATES = {"completed", "failed", "cancelled", "expired"}


def job_stage_timeline(job_type: str, status: str) -> list[dict[str, str]]:
    """Build the ordered stage timeline for a job (PRD §10.4). Pure.

    Each step is ``{stage, state, label}`` where ``state`` is one of
    done / current / pending / skipped. A failed/cancelled job marks the last
    reached step as that terminal state and the rest pending.
    """
    pipeline = _JOB_PIPELINES.get(job_type, _DEFAULT_PIPELINE)
    stages = [s for s, _ in pipeline]

    # Terminal non-success: the job stopped wherever it was. We can't always
    # know the exact stage, so map failed/cancelled onto the "completed" slot
    # visually by flagging every prior stage done and the final one failed.
    if status in ("failed", "cancelled", "expired"):
        steps = []
        for stage, label in pipeline[:-1]:
            steps.append({"stage": stage, "state": "done", "label": label})
        steps.append({"stage": status, "state": status, "label": status.capitalize()})
        return steps

    # Find how far along we are. If the status isn't in the pipeline (e.g. a
    # preview status on a process job), treat it as in-progress at index 1.
    idx = stages.index(status) if status in stages else min(1, len(stages) - 1)
    steps = []
    for i, (stage, label) in enumerate(pipeline):
        if i < idx:
            state = "done"
        elif i == idx:
            state = "done" if status == "completed" else "current"
        else:
            state = "pending"
        steps.append({"stage": stage, "state": state, "label": label})
    return steps


def is_terminal_job_state(status: str) -> bool:
    return status in _TERMINAL_STATES


# --- Admin Panel Phase 4: billing / payments / subscriptions / plans /
#     promos / credits (PRD §13–17). All pure — unit-tested on 32-bit. ---

# PRD §13.3 payment statuses + §14.3 subscription statuses + §16 discount types.
PAYMENT_STATUSES = (
    "created", "authorized", "captured", "failed",
    "refunded", "partially_refunded", "disputed", "sandbox",
)
SUBSCRIPTION_STATUSES = (
    "trialing", "active", "paused", "past_due", "pending",
    "cancelled", "expired", "completed",
)
DISCOUNT_TYPES = (
    "fixed", "percentage", "free_trial_extension",
    "bonus_credits", "first_cycle", "multi_cycle",
)
BILLING_INTERVALS = ("monthly", "annual", "quarterly")

# Refunds at or above this fraction of the original charge require super-admin
# approval (PRD §13.5). Kept as a constant so both the guard and the frontend
# hint agree; overridable per deployment via config later.
REFUND_SUPER_ADMIN_THRESHOLD_INR = 500_000  # ₹5,000 in paise


def mask_secret(value: Optional[str], *, keep: int = 4) -> Optional[str]:
    """Mask a sensitive identifier for display (PRD §13.4, §33.2). Keeps the
    last ``keep`` characters, masking the rest. ``None`` stays ``None``; short
    values are fully masked."""
    if not value:
        return value
    if len(value) <= keep:
        return "•" * len(value)
    return "•" * (len(value) - keep) + value[-keep:]


def refund_requires_approval(
    amount_inr: int,
    *,
    actor_role: Optional[str],
    threshold_inr: int = REFUND_SUPER_ADMIN_THRESHOLD_INR,
) -> bool:
    """True when a refund of ``amount_inr`` (paise) needs super-admin approval
    and the acting admin is not a super_admin (PRD §13.5)."""
    if amount_inr >= threshold_inr and actor_role != "super_admin":
        return True
    return False


def validate_refund(
    *,
    amount_inr: int,
    payment_amount_inr: int,
    already_refunded_inr: int,
) -> str:
    """Validate a refund amount against the payment. Returns the refund kind
    ('full' | 'partial'). Raises ValueError on an invalid amount."""
    if amount_inr <= 0:
        raise ValueError("refund amount must be positive")
    remaining = payment_amount_inr - already_refunded_inr
    if amount_inr > remaining:
        raise ValueError("refund exceeds the refundable balance")
    return "full" if amount_inr >= remaining else "partial"


def refund_status_after(payment_amount_inr: int, total_refunded_inr: int) -> str:
    """Map cumulative refunds to a payment refund_status label."""
    if total_refunded_inr <= 0:
        return "none"
    if total_refunded_inr >= payment_amount_inr:
        return "full"
    return "partial"


def billing_overview(
    counts: Mapping[str, Any],
    *,
    active_subscriptions: int = 0,
) -> dict[str, Any]:
    """Shape the billing dashboard payload (PRD §13.1) from raw aggregates.
    Amounts arrive in paise and are echoed in paise (frontend divides by 100).
    ARPU is revenue_this_month / active_subscriptions (0 when no subs)."""
    revenue_month = int(counts.get("revenue_this_month_inr", 0) or 0)
    subs = int(active_subscriptions or 0)
    arpu = revenue_month // subs if subs > 0 else 0
    return {
        "revenue_today_inr": int(counts.get("revenue_today_inr", 0) or 0),
        "revenue_month_inr": revenue_month,
        "mrr_inr": revenue_month,  # monthly plans → MRR ≈ this month's recurring revenue
        "active_subscriptions": subs,
        "new_subscriptions": int(counts.get("new_subscriptions", 0) or 0),
        "renewals": int(counts.get("renewals", 0) or 0),
        "cancellations": int(counts.get("cancellations", 0) or 0),
        "failed_payments": int(counts.get("failed_payments", 0) or 0),
        "refunds_inr": int(counts.get("refunds_inr", 0) or 0),
        "arpu_inr": arpu,
    }


def promo_remaining_uses(max_total_uses: Optional[int], times_redeemed: int) -> Optional[int]:
    """Remaining redemptions for a promo (PRD §16.3). None = unlimited."""
    if max_total_uses is None:
        return None
    return max(0, max_total_uses - int(times_redeemed or 0))


def validate_plan_fields(
    *,
    price_inr: int,
    credits_per_day: int,
    billing_interval: Optional[str] = None,
    discount_free: bool = False,
) -> None:
    """Validate plan create/edit inputs (PRD §15.2). Raises ValueError."""
    if price_inr < 0:
        raise ValueError("price must be non-negative")
    if credits_per_day < 0:
        raise ValueError("credits_per_day must be non-negative")
    if billing_interval is not None and billing_interval not in BILLING_INTERVALS:
        raise ValueError(f"billing_interval must be one of {', '.join(BILLING_INTERVALS)}")


def validate_promo_fields(
    *,
    discount_type: str,
    discount_value: Optional[int],
    max_total_uses: Optional[int] = None,
    max_uses_per_user: Optional[int] = None,
) -> None:
    """Validate promo create/edit inputs (PRD §16.1). Raises ValueError."""
    if discount_type not in DISCOUNT_TYPES:
        raise ValueError(f"discount_type must be one of {', '.join(DISCOUNT_TYPES)}")
    if discount_value is not None and discount_value < 0:
        raise ValueError("discount_value must be non-negative")
    if discount_type == "percentage" and discount_value is not None and discount_value > 100:
        raise ValueError("percentage discount cannot exceed 100")
    for label, v in (("max_total_uses", max_total_uses), ("max_uses_per_user", max_uses_per_user)):
        if v is not None and v < 0:
            raise ValueError(f"{label} must be non-negative")


def credit_dashboard(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate today's credit-ledger rows into the credit dashboard
    (PRD §17.1). Each row: {direction, amount, source}. Splits issued vs
    consumed vs refunded vs bonus by source/direction."""
    issued = consumed = refunded = bonus = 0
    for r in rows:
        amount = int(r.get("amount", 0) or 0)
        direction = r.get("direction")
        source = r.get("source")
        if direction == "credit":
            issued += amount
            if source == "refund":
                refunded += amount
            elif source in ("admin", "subscription"):
                bonus += amount
        elif direction == "debit":
            consumed += amount
    return {
        "credits_issued_today": issued,
        "credits_consumed_today": consumed,
        "credits_refunded_today": refunded,
        "bonus_credits_today": bonus,
    }


def subscription_display_status(
    status: str,
    *,
    cancel_at_period_end: bool = False,
    grace_until: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> str:
    """Derive the label shown in the subscription list (PRD §14.3). A grace
    window shows 'past_due'; a pending cancellation is still 'active' but the
    UI flags cancel-at-period-end separately."""
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    if grace_until is not None:
        gu = grace_until if grace_until.tzinfo else grace_until.replace(tzinfo=timezone.utc)
        if gu > ref and status not in ("cancelled", "expired"):
            return "past_due"
    return status


# Webhook payload keys whose values are gateway secrets / PII and must never
# reach the browser in the clear (PRD §13.4, §33.2).
_WEBHOOK_SENSITIVE_KEYS = frozenset({
    "token", "card", "card_id", "vpa", "email", "contact", "customer_id",
    "bank_account", "auth_code", "signature", "secret", "notes",
})


def mask_webhook_payload(payload: Any) -> Any:
    """Recursively mask sensitive keys in a Razorpay webhook payload before it
    is shown to an admin (PRD §13.4). Non-dict/list values pass through; keys in
    ``_WEBHOOK_SENSITIVE_KEYS`` have their scalar values masked."""
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for k, v in payload.items():
            if k in _WEBHOOK_SENSITIVE_KEYS and isinstance(v, (str, int)):
                out[k] = mask_secret(str(v))
            else:
                out[k] = mask_webhook_payload(v)
        return out
    if isinstance(payload, list):
        return [mask_webhook_payload(v) for v in payload]
    return payload



def retention_deltas(
    *,
    retain_original_hours: int,
    retain_preview_hours: int,
    retain_output_days: int,
    retain_failed_hours: int,
    now: Optional[datetime] = None,
) -> dict[str, datetime]:
    """Compute the expiry cutoff timestamps for each artifact class.

    STORAGE-006: original 24h, preview 24h, output 7d, failed-job temp 6h,
    frames immediate. Returns the *cutoff* — artifacts older than this are
    eligible for deletion. Frames are deleted immediately after encode, so
    they have no cutoff here (handled at job completion).
    """
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return {
        "original": ref - timedelta(hours=retain_original_hours),
        "preview": ref - timedelta(hours=retain_preview_hours),
        "output": ref - timedelta(days=retain_output_days),
        "failed": ref - timedelta(hours=retain_failed_hours),
    }


# --- Admin Panel Phase 5: storage & compliance (pure) ---

# Storage buckets surfaced on the dashboard (PRD §18.1/§18.2). ``key_attr`` is
# the VideoProject column that carries a key in that bucket; ``frames`` and
# ``orphaned`` have no per-project column and are estimated separately.
STORAGE_BUCKETS = ("input", "proxy", "preview", "output", "mask", "thumbnail")

# Abuse report lifecycle (PRD §21.3).
ABUSE_STATUSES = (
    "new",
    "under_review",
    "waiting_for_information",
    "action_required",
    "resolved",
    "rejected",
    "escalated",
    "legal_hold",
)

# Compliance/legal actions on a report + its project (PRD §21.5).
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

# Severity buckets (PRD §21.2).
ABUSE_SEVERITIES = ("low", "medium", "high", "critical")

# Per-storage-bucket cost estimate, micro-INR per GB-month, so the dashboard can
# show an approximate spend without wiring a billing provider (PRD §18.1). Value
# is deliberately conservative; overridable via config later.
STORAGE_COST_MICRO_INR_PER_GB = 2_000_000  # ₹2.00 / GB-month


def storage_overview(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate per-bucket byte totals into the §18.1 storage overview.

    Each row is ``{"bucket": str, "bytes": int}`` (already grouped in SQL). Any
    bucket not present defaults to zero. ``total_bytes`` sums every bucket and
    ``estimated_cost_inr`` applies the flat per-GB rate (returned in paise).
    """
    by_bucket: dict[str, int] = {b: 0 for b in STORAGE_BUCKETS}
    by_bucket["frames"] = 0
    by_bucket["orphaned"] = 0
    for row in rows:
        bucket = str(row.get("bucket", "")).strip()
        b = int(row.get("bytes", 0) or 0)
        if bucket in by_bucket:
            by_bucket[bucket] += b
        else:
            by_bucket["orphaned"] += b
    total = sum(by_bucket.values())
    gb = total / (1024 ** 3)
    estimated_cost_inr = int(round(gb * STORAGE_COST_MICRO_INR_PER_GB / 10_000))  # micro-INR→paise
    return {
        "total_bytes": total,
        "buckets": by_bucket,
        "estimated_cost_inr": estimated_cost_inr,
    }


def storage_deletion_allowed(
    *,
    has_active_job: bool,
    legal_hold: bool,
    locked: bool,
    has_open_dispute: bool,
) -> tuple[bool, Optional[str]]:
    """PRD §18.5 delete-safety guard. Returns ``(allowed, blocking_reason)``.

    The system must refuse to delete files that are (in priority order) used by
    an active job, on legal hold, locked for compliance, or tied to an
    unresolved billing/support dispute.
    """
    if has_active_job:
        return False, "active_job"
    if legal_hold:
        return False, "legal_hold"
    if locked:
        return False, "compliance_lock"
    if has_open_dispute:
        return False, "open_dispute"
    return True, None


def retention_bucket(
    expires_at: Optional[datetime],
    *,
    legal_hold: bool = False,
    retention_extended: bool = False,
    cleanup_failed: bool = False,
    now: Optional[datetime] = None,
) -> str:
    """Classify a file for the retention dashboard (PRD §18.3).

    Precedence: locked-for-compliance (legal hold) and failed-cleanup win over
    the time-based buckets so an admin sees the exceptional states first.
    Returns one of: locked | failed_cleanup | past_retention | expiring_today |
    expiring_soon | extended | active.
    """
    if legal_hold:
        return "locked"
    if cleanup_failed:
        return "failed_cleanup"
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    if expires_at is not None:
        exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
        if exp <= ref:
            return "past_retention"
        if exp <= ref + timedelta(hours=24):
            return "expiring_today"
        if exp <= ref + timedelta(days=7):
            return "expiring_soon"
    if retention_extended:
        return "extended"
    return "active"


def validate_abuse_severity(severity: str) -> str:
    """Normalise + validate an abuse severity; raises AppError(422) on unknown."""
    s = (severity or "").strip().lower()
    if s not in ABUSE_SEVERITIES:
        from app.core.errors import AppError

        raise AppError("VALIDATION_ERROR", f"severity must be one of {ABUSE_SEVERITIES}", 422)
    return s


def compliance_action_effects(action: str) -> dict[str, Any]:
    """Map a §21.5 compliance action to its side effects on the report + project.

    Pure lookup so the route/orchestration layer stays declarative and the
    mapping is unit-testable. Keys:
      * ``report_status``    — new abuse_reports.status (None = unchanged)
      * ``project`` (dict)   — VideoProject field patches (None values ignored)
      * ``account_status``   — AccountStatus to set on the owner (None = none)
      * ``requires_reason``  — destructive/records-needing-justification actions
    """
    if action not in COMPLIANCE_ACTIONS:
        from app.core.errors import AppError

        raise AppError("VALIDATION_ERROR", f"action must be one of {COMPLIANCE_ACTIONS}", 422)

    effects: dict[str, Any] = {
        "report_status": None,
        "project": {},
        "account_status": None,
        "requires_reason": False,
    }
    if action == "mark_safe":
        effects["report_status"] = "resolved"
    elif action == "request_information":
        effects["report_status"] = "waiting_for_information"
    elif action == "restrict_processing":
        effects["report_status"] = "action_required"
        effects["project"] = {"processing_restricted": True}
    elif action == "disable_downloads":
        effects["report_status"] = "action_required"
        effects["project"] = {"downloads_disabled": True}
    elif action == "suspend_account":
        effects["report_status"] = "action_required"
        effects["account_status"] = "suspended"
        effects["requires_reason"] = True
    elif action == "ban_account":
        effects["report_status"] = "action_required"
        effects["account_status"] = "banned"
        effects["requires_reason"] = True
    elif action == "place_legal_hold":
        effects["report_status"] = "legal_hold"
        effects["project"] = {"legal_hold": True, "locked": True}
        effects["requires_reason"] = True
    elif action == "remove_legal_hold":
        effects["project"] = {"legal_hold": False}
        effects["requires_reason"] = True
    elif action == "escalate":
        effects["report_status"] = "escalated"
    elif action == "add_note":
        effects["requires_reason"] = True  # the note text is carried in reason
    elif action == "close":
        effects["report_status"] = "resolved"
    return effects


def compliance_overview(counts: Mapping[str, Any]) -> dict[str, Any]:
    """Shape the §21.1 compliance overview from a pre-aggregated counts dict.

    Pure pass-through with defaults so the route can hand raw SQL counts
    straight in and every field is always present.
    """
    return {
        "ownership_confirmations": int(counts.get("ownership_confirmations", 0) or 0),
        "projects_reported": int(counts.get("projects_reported", 0) or 0),
        "open_reviews": int(counts.get("open_reviews", 0) or 0),
        "suspended_accounts": int(counts.get("suspended_accounts", 0) or 0),
        "repeat_offenders": int(counts.get("repeat_offenders", 0) or 0),
        "high_risk_uploads": int(counts.get("high_risk_uploads", 0) or 0),
        "missing_confirmations": int(counts.get("missing_confirmations", 0) or 0),
        "projects_on_legal_hold": int(counts.get("projects_on_legal_hold", 0) or 0),
    }


# ---------------------------------------------------------------------------
# Phase 6 — AI models, presets, feature flags, notifications, maintenance (pure)
# ---------------------------------------------------------------------------

MODEL_TYPES = (
    "watermark_detection",
    "ocr_detection",
    "segmentation",
    "static_tracking",
    "moving_tracking",
    "image_inpainting",
    "temporal_video_inpainting",
    "artifact_detection",
    "quality_validation",
)

MODEL_STATUSES = (
    "active",
    "testing",
    "disabled",
    "deprecated",
    "maintenance",
    "rollback_candidate",
)

MODEL_ACTIONS = (
    "enable_testing",
    "enable_production",
    "disable",
    "set_default",
    "set_fallback",
    "rollback",
    "deprecate",
)

ROLLOUT_STRATEGIES = ("internal", "selected_users", "percentage", "plans", "full")

# Model lifecycle transitions (§19.4). Maps an admin action to the status it
# produces; a value of None means "status unchanged" (flag-only actions).
_MODEL_ACTION_STATUS = {
    "enable_testing": "testing",
    "enable_production": "active",
    "disable": "disabled",
    "deprecate": "deprecated",
    "rollback": "rollback_candidate",
    "set_default": None,
    "set_fallback": None,
}

NOTIFICATION_TEMPLATE_KEYS = (
    "email_verification",
    "password_reset",
    "job_completed",
    "job_failed",
    "low_credit",
    "payment_successful",
    "payment_failed",
    "subscription_renewed",
    "subscription_cancelled",
    "output_expiring",
    "account_suspended",
    "maintenance_announcement",
)

BROADCAST_KINDS = ("in_app", "maintenance", "feature", "billing", "policy")

BROADCAST_TARGETS = (
    "all",
    "specific_plan",
    "active_subscribers",
    "free_users",
    "selected_users",
    "users_with_active_jobs",
)

# Canonical feature-flag catalogue (§26.5). Seeded/merged so the UI always
# shows the full set even before any row exists.
FEATURE_FLAG_KEYS = (
    "automatic_watermark_detection",
    "moving_watermark_tracking",
    "multiple_masks",
    "promo_codes",
    "razorpay_checkout",
    "billing_portal",
    "google_authentication",
    "high_quality_processing",
    "user_issue_reporting",
    "new_project_creation",
)

MAINTENANCE_SETTING_KEY = "maintenance"

# Maintenance-mode state defaults (§26.6). Stored as JSON in system_settings.
MAINTENANCE_DEFAULTS: dict[str, Any] = {
    "maintenance_enabled": False,
    "start_time": None,
    "end_time": None,
    "public_message": "",
    "allow_administrators": True,
    "allow_existing_jobs_to_finish": True,
    "pause_new_uploads": True,
    "pause_new_processing_jobs": True,
    "disable_checkout": False,
    "status_page_link": None,
}


def _label_from_key(key: str) -> str:
    """Humanise a snake_case key: ``moving_watermark_tracking`` → 'Moving Watermark Tracking'."""
    return key.replace("_", " ").strip().title()


def validate_model_type(model_type: str) -> str:
    """Normalise + validate an AI model type; raises AppError(422) on unknown."""
    value = (model_type or "").strip().lower()
    if value not in MODEL_TYPES:
        raise AppError("VALIDATION_ERROR", f"model_type must be one of {MODEL_TYPES}", 422)
    return value


def validate_model_action(action: str) -> str:
    """Validate a model lifecycle action; raises AppError(422) on unknown."""
    value = (action or "").strip().lower()
    if value not in MODEL_ACTIONS:
        raise AppError("VALIDATION_ERROR", f"action must be one of {MODEL_ACTIONS}", 422)
    return value


def model_action_effects(action: str) -> dict[str, Any]:
    """Pure decision for a model lifecycle action (§19.4).

    Returns the intended mutation: ``status`` (or None to leave unchanged),
    ``is_default``/``is_fallback`` flags to set (or None), and whether the
    action needs a reason. ``rollback`` and ``enable_production`` are the
    consequential ones — a production promotion clears any prior testing state
    and a rollback marks the version as a rollback candidate.
    """
    action = validate_model_action(action)
    effects: dict[str, Any] = {
        "status": _MODEL_ACTION_STATUS.get(action),
        "set_default": True if action == "set_default" else None,
        "set_fallback": True if action == "set_fallback" else None,
        "requires_reason": action in ("rollback", "disable", "deprecate"),
    }
    return effects


def validate_rollout(strategy: str, percentage: int | None) -> tuple[str, int]:
    """Validate a staged-rollout config (§19.5).

    ``percentage`` is only meaningful for the ``percentage`` strategy and must
    be 0–100; other strategies coerce it to 0. Raises AppError(422).
    """
    value = (strategy or "").strip().lower()
    if value not in ROLLOUT_STRATEGIES:
        raise AppError("VALIDATION_ERROR", f"rollout_strategy must be one of {ROLLOUT_STRATEGIES}", 422)
    if value == "percentage":
        pct = int(percentage or 0)
        if not 0 <= pct <= 100:
            raise AppError("VALIDATION_ERROR", "rollout_percentage must be between 0 and 100", 422)
        return value, pct
    return value, 0


def validate_preset_fields(
    *,
    name: str | None,
    frame_sampling_rate: int | None = None,
    mask_expansion: int | None = None,
    feathering: int | None = None,
    encoding_quality: int | None = None,
    expected_credit_cost: int | None = None,
) -> None:
    """Validate processing-preset numeric bounds (§20.2). Raises AppError(422)."""
    if not name or not name.strip():
        raise AppError("VALIDATION_ERROR", "Preset name is required.", 422)
    if frame_sampling_rate is not None and frame_sampling_rate < 1:
        raise AppError("VALIDATION_ERROR", "frame_sampling_rate must be >= 1.", 422)
    if mask_expansion is not None and mask_expansion < 0:
        raise AppError("VALIDATION_ERROR", "mask_expansion cannot be negative.", 422)
    if feathering is not None and feathering < 0:
        raise AppError("VALIDATION_ERROR", "feathering cannot be negative.", 422)
    if encoding_quality is not None and not 0 <= encoding_quality <= 100:
        raise AppError("VALIDATION_ERROR", "encoding_quality must be between 0 and 100.", 422)
    if expected_credit_cost is not None and expected_credit_cost < 0:
        raise AppError("VALIDATION_ERROR", "expected_credit_cost cannot be negative.", 422)


def merge_feature_flags(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Overlay stored flag rows onto the canonical §26.5 catalogue.

    Any catalogue key without a row shows as enabled-by-default with a derived
    label; stored rows win. The result is ordered by the catalogue so the UI is
    stable regardless of insertion order. Unknown stored keys are appended.
    """
    by_key = {r["key"]: r for r in rows if r.get("key")}
    out: list[dict[str, Any]] = []
    for key in FEATURE_FLAG_KEYS:
        row = by_key.pop(key, None)
        out.append({
            "key": key,
            "label": (row or {}).get("label") or _label_from_key(key),
            "enabled": bool((row or {}).get("enabled", True)),
            "description": (row or {}).get("description"),
        })
    # Preserve any extra flags that exist in the DB but not in the catalogue.
    for key, row in by_key.items():
        out.append({
            "key": key,
            "label": row.get("label") or _label_from_key(key),
            "enabled": bool(row.get("enabled", True)),
            "description": row.get("description"),
        })
    return out


def normalise_maintenance(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge a stored maintenance blob onto the §26.6 defaults.

    Always returns every field so the admin form and the public gate can read a
    complete object even before maintenance has ever been configured.
    """
    merged = dict(MAINTENANCE_DEFAULTS)
    if state:
        for key in MAINTENANCE_DEFAULTS:
            if key in state and state[key] is not None:
                merged[key] = state[key]
    merged["maintenance_enabled"] = bool(merged["maintenance_enabled"])
    return merged


def validate_broadcast(kind: str, target: str) -> tuple[str, str]:
    """Validate a broadcast kind + target segment (§23.3). Raises AppError(422)."""
    k = (kind or "").strip().lower()
    if k not in BROADCAST_KINDS:
        raise AppError("VALIDATION_ERROR", f"kind must be one of {BROADCAST_KINDS}", 422)
    t = (target or "all").strip().lower()
    if t not in BROADCAST_TARGETS:
        raise AppError("VALIDATION_ERROR", f"target must be one of {BROADCAST_TARGETS}", 422)
    return k, t


def render_template_preview(template: Mapping[str, Any], variables: Mapping[str, Any]) -> dict[str, str]:
    """Substitute ``{{var}}`` placeholders in a template's subject/body (§23.1).

    Pure string interpolation — no HTML sanitisation here (the stored content is
    admin-authored and trusted). Missing variables are left as the literal
    placeholder so the author can see what still needs a value.
    """
    def _apply(text: str) -> str:
        out = text or ""
        for key, value in variables.items():
            out = out.replace("{{" + str(key) + "}}", str(value))
        return out

    return {
        "subject": _apply(str(template.get("subject", ""))),
        "html_content": _apply(str(template.get("html_content", ""))),
        "text_content": _apply(str(template.get("text_content", ""))),
    }





def is_brittle_region(mask_geometry: Mapping[str, Any], *, frame_width: int, frame_height: int) -> bool:
    """RECON-008: flag masks that cover faces/hands/high-variance regions.

    A precise face/hand detector is out of MVP scope. As a conservative
    heuristic, a mask is flagged brittle when it covers a large fraction of
    the frame (>35% area) — large inpaint regions are the ones that produce
    visible artifacts on skin/texture. The frontend shows a warning banner.
    """
    bb = _mask_bbox(mask_geometry)
    if bb is None or not frame_width or not frame_height:
        return False
    x, y, w, h = bb
    area = w * h
    frame_area = frame_width * frame_height
    if frame_area <= 0:
        return False
    return (area / frame_area) > 0.35


def _mask_bbox(geo: Mapping[str, Any]) -> Optional[tuple[float, float, float, float]]:
    tool = geo.get("tool")
    if tool == "rectangle":
        try:
            return float(geo["x"]), float(geo["y"]), float(geo["w"]), float(geo["h"])
        except (KeyError, TypeError, ValueError):
            return None
    if tool == "polygon":
        # The editor stores points as `points`; candidate_to_mask writes
        # `vertices`. Accept both so the brittle check covers promoted candidates.
        verts = geo.get("points") or geo.get("vertices") or []
        if len(verts) < 3:
            return None
        try:
            xs = [float(v[0]) for v in verts]
            ys = [float(v[1]) for v in verts]
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        return x0, y0, (x1 - x0), (y1 - y0)
    if tool == "brush":
        # brush strokes store a list of {x,y,r} discs — bbox the union. The
        # editor key is `strokes`; `discs` is the legacy/alternate name.
        discs = geo.get("strokes") or geo.get("discs") or []
        if not discs:
            return None
        try:
            xs, ys, rs = [], [], []
            for d in discs:
                xs.append(float(d["x"]))
                ys.append(float(d["y"]))
                rs.append(float(d.get("r", 0)))
        except (KeyError, TypeError, ValueError, IndexError):
            return None
        x0 = min(x - r for x, r in zip(xs, rs))
        x1 = max(x + r for x, r in zip(xs, rs))
        y0 = min(y - r for y, r in zip(ys, rs))
        y1 = max(y + r for y, r in zip(ys, rs))
        return x0, y0, (x1 - x0), (y1 - y0)
    if tool == "multi":
        # composite mask — union of the sub-shape bboxes
        boxes = []
        for sub in geo.get("shapes") or []:
            if not isinstance(sub, Mapping):
                continue
            sub_geo = dict(sub.get("geometry") or {})
            sub_geo["tool"] = sub.get("tool")
            b = _mask_bbox(sub_geo)
            if b is not None:
                boxes.append(b)
        if not boxes:
            return None
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes)
        y1 = max(b[1] + b[3] for b in boxes)
        return x0, y0, (x1 - x0), (y1 - y0)
    return None


# --- Orchestration (DB-backed) ---


def _runtime_imports():
    """Lazy import of the ORM + repo layer. These pull SQLAlchemy, which isn't
    installed on the 32-bit dev box — so they live behind this helper and are
    only resolved when an orchestration function actually runs (64-bit env)."""
    from app.models import AccountStatus, JobState, User
    from app.repositories import admin as admin_repo
    from app.repositories import processing as proc_repo
    return AccountStatus, JobState, User, admin_repo, proc_repo


def get_overview(db: "Session", heartbeats: Mapping[str, int]) -> dict[str, Any]:
    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    counts = admin_repo.overview_counts(db)
    counts["queue_length"] = admin_repo.queue_length(db)
    counts["gpu_workers"] = admin_repo.gpu_worker_count(db)
    counts["storage_bytes"] = admin_repo.storage_bytes(db)
    # PRD §7.2 business metrics.
    counts.update(admin_repo.counts_today_and_month(db))
    counts.update(overview_extras(counts))
    return counts


def get_workers(db: "Session", heartbeats: Mapping[str, int]) -> list[WorkerInfo]:
    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    return fuse_workers(admin_repo.list_worker_nodes(db), heartbeats)


def apply_user_action(
    db: "Session", *, admin: "User", target: "User", action: str
) -> "User":
    AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    if action == "suspend":
        admin_repo.set_account_status(db, target, AccountStatus.suspended)
        admin_repo.record_audit(
            db, actor_id=admin.id, action="user.suspend",
            target_type="user", target_id=target.id,
            details=audit_details("user.suspend", email=target.email),
        )
    else:  # reactivate
        admin_repo.set_account_status(db, target, AccountStatus.active)
        admin_repo.record_audit(
            db, actor_id=admin.id, action="user.reactivate",
            target_type="user", target_id=target.id,
            details=audit_details("user.reactivate", email=target.email),
        )
    return target


def apply_job_action(
    db: "Session", *, admin: "User", job: "ProcessingJob", action: str
) -> "ProcessingJob":
    """ADMIN-003 retry / cancel. Retry re-enqueues on the job's queue; cancel
    moves the row to a terminal ``cancelled`` state (only legal from non-terminal)."""
    _AccountStatus, JobState, _User, admin_repo, proc_repo = _runtime_imports()
    if action == "cancel":
        if job.status in (JobState.completed, JobState.failed, JobState.cancelled, JobState.expired):
            from app.core.errors import AppError
            raise AppError("CONFLICT", f"Cannot cancel a {job.status.value} job.", 409)
        proc_repo.transition(db, job, JobState.cancelled, stage="cancelled")
        admin_repo.record_audit(
            db, actor_id=admin.id, action="job.cancel",
            target_type="job", target_id=job.id,
            details=audit_details("job.cancel", project_id=job.project_id),
        )
        return job
    # retry
    if job.status not in (JobState.failed, JobState.cancelled):
        from app.core.errors import AppError
        raise AppError("CONFLICT", "Only failed or cancelled jobs can be retried.", 409)
    # Re-arm directly to processing_queued: the workers pick jobs up from that
    # state (created -> processing is not a legal transition, so re-enqueueing
    # a `created` job would instantly fail with "illegal job transition").
    job.status = JobState.processing_queued
    job.error_code = None
    job.error_message = None
    job.completed_at = None
    job.attempt_count = (job.attempt_count or 0) + 1
    db.flush()
    admin_repo.record_audit(
        db, actor_id=admin.id, action="job.retry",
        target_type="job", target_id=job.id,
        details=audit_details("job.retry", project_id=job.project_id, attempt=job.attempt_count),
    )
    return job


def apply_abuse_action(
    db: "Session", *, admin: "User", report, action: str
):
    """ADMIN-007 dismiss / escalate / suspend_reporter. Returns (report, target_user)."""
    from app.core.errors import AppError

    AccountStatus, _JobState, User, admin_repo, _proc_repo = _runtime_imports()
    status_map = {"dismiss": "dismissed", "escalate": "escalated", "suspend_reporter": "actioned"}
    admin_repo.set_abuse_status(db, report, status_map[action])
    target_user: Optional[User] = None
    if action == "suspend_reporter" and report.reported_by:
        target_user = db.get(User, report.reported_by)
        if target_user is not None:
            admin_repo.set_account_status(db, target_user, AccountStatus.suspended)
    elif action == "suspend_reporter":
        raise AppError("NOT_FOUND", "No reporter on this report to suspend.", 404)
    admin_repo.record_audit(
        db, actor_id=admin.id, action=f"abuse.{action}",
        target_type="abuse_report", target_id=report.id,
        details=audit_details(f"abuse.{action}", project_id=report.project_id),
    )
    return report, target_user


def apply_subscription_action(
    db: "Session",
    *,
    admin: "User",
    subscription,
    action: str,
    plan_id: Optional[str] = None,
    reason: Optional[str] = None,
    audit_ctx: Optional[dict] = None,
):
    """PRD §14.4 subscription actions — cancel (immediate), cancel_at_period_end,
    resume, reactivate, change_plan. Mutates the row + writes an audit trail.
    The caller commits."""
    from app.core.errors import AppError

    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    from app.models import SubscriptionStatus

    def _status_value(s) -> str:
        return s.value if hasattr(s, "value") else str(s)

    prev = {
        "status": _status_value(subscription.status),
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "plan_id": subscription.plan_id,
    }
    ctx = audit_ctx or {}

    if action == "cancel":
        subscription.status = SubscriptionStatus.cancelled
        subscription.cancel_at_period_end = False
        subscription.cancelled_at = datetime.now(timezone.utc)
    elif action == "cancel_at_period_end":
        subscription.cancel_at_period_end = True
    elif action == "resume":
        # Undo a pending cancellation.
        subscription.cancel_at_period_end = False
        subscription.cancelled_at = None
        if _status_value(subscription.status) in ("cancelled", "paused"):
            subscription.status = SubscriptionStatus.active
    elif action == "reactivate":
        if _status_value(subscription.status) not in ("cancelled", "expired", "paused"):
            raise AppError("CONFLICT", "Only cancelled/expired/paused subscriptions can be reactivated.", 409)
        subscription.status = SubscriptionStatus.active
        subscription.cancel_at_period_end = False
        subscription.cancelled_at = None
        subscription.payment_failures = 0
    elif action == "change_plan":
        if not plan_id or admin_repo.get_plan(db, plan_id) is None:
            raise AppError("NOT_FOUND", "Target plan not found.", 404)
        subscription.plan_id = plan_id
    else:  # pragma: no cover — schema validates the vocabulary
        raise AppError("INVALID_ACTION", f"Unknown subscription action '{action}'.", 422)

    db.flush()
    admin_repo.record_audit(
        db, actor_id=admin.id, action=f"subscription.{action}",
        target_type="subscription", target_id=subscription.id,
        previous_data=prev,
        new_data={
            "status": _status_value(subscription.status),
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "plan_id": subscription.plan_id,
        },
        reason=reason, **ctx,
    )
    return subscription


# --- Admin Panel Phases 1+2: orchestration ---


def build_audit_context(request) -> dict[str, Any]:
    """Extract request-scoped audit fields (PRD §27.2) from a FastAPI Request.
    Tolerates missing state/client so it's safe from any handler."""
    from app.services.compliance import hash_ip

    client_ip = None
    try:
        client_ip = request.client.host if request.client else None
    except Exception:  # noqa: BLE001
        client_ip = None
    return {
        "ip_hash": hash_ip(client_ip),
        "user_agent": (request.headers.get("user-agent") or None) if request.headers else None,
        "request_id": getattr(getattr(request, "state", None), "request_id", None),
    }


def get_user_detail(db: "Session", user: "User") -> dict[str, Any]:
    """Assemble the GET /admin/users/{id} bundle (PRD §8.3 header + profile)."""
    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    projects, jobs = admin_repo.usage_counts(db, user.id)
    extras = admin_repo.user_detail_extras(db, user.id)
    sub = user.subscription
    ledger = user.credit_ledger
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "admin_role": user.admin_role,
        "account_status": user.account_status.value,
        "email_verified": user.email_verified,
        "created_at": user.created_at,
        "plan_id": user.plan_id or "free",
        "plan_name": user.plan.name if user.plan else "Free",
        "credits_remaining": user.credits_remaining,
        "credits_limit": ledger.credits_limit if ledger else None,
        "credits_used_today": ledger.credits_used_today if ledger else None,
        "project_count": projects,
        "job_count": jobs,
        "failed_job_count": extras["failed_jobs"],
        "storage_bytes": extras["storage_bytes"],
        "active_session_count": extras["active_sessions"],
        "subscription": None if sub is None else {
            "id": sub.id,
            "plan_id": sub.plan_id,
            "status": sub.status.value,
            "razorpay_subscription_id": sub.razorpay_subscription_id,
            "current_period_start": sub.current_period_start,
            "current_period_end": sub.current_period_end,
            "cancelled_at": sub.cancelled_at,
            "created_at": sub.created_at,
        },
    }


def adjust_credits(
    db: "Session",
    *,
    admin: "User",
    target: "User",
    amount: int,
    direction: str,
    reason: str,
    reference: Optional[str] = None,
    audit_ctx: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Admin credit adjustment (PRD §8.4/§17.4): locked balance update + an
    immutable credit_transactions row + audit entry. Raises AppError 409 on
    overdraft."""
    from app.core.errors import AppError

    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    locked = admin_repo.get_user_locked(db, target.id)
    try:
        txn = build_credit_txn(
            user_id=target.id,
            balance_before=locked.credits_remaining,
            amount=amount,
            direction=direction,
            source="admin",
            reason=reason if not reference else f"{reason} (ref: {reference})",
            admin_id=admin.id,
        )
    except ValueError as exc:
        raise AppError("CONFLICT", str(exc), 409) from exc
    locked.credits_remaining = txn["balance_after"]
    row = admin_repo.insert_credit_txn(db, **txn)
    admin_repo.record_audit(
        db, actor_id=admin.id, action="user.credits_adjust",
        target_type="user", target_id=target.id,
        details=audit_details("user.credits_adjust", amount=amount, direction=direction),
        previous_data={"credits_remaining": txn["balance_before"]},
        new_data={"credits_remaining": txn["balance_after"]},
        reason=reason,
        **(audit_ctx or {}),
    )
    return {"transaction": row, "balance": txn["balance_after"]}


def change_admin_role(
    db: "Session", *, admin: "User", target: "User",
    new_role: Optional[str], audit_ctx: Optional[Mapping[str, Any]] = None,
) -> "User":
    """Assign/clear the admin-panel role (PRD §28.2). Only super admins may
    call this (enforced by the route permission); guards against removing the
    last super_admin."""
    from app.core.errors import AppError
    from app.services.admin_permissions import effective_admin_role

    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    prev = target.admin_role
    was_super = effective_admin_role(target.role.value, target.admin_role) == "super_admin"
    if was_super and new_role != "super_admin":
        if admin_repo.count_super_admins(db, exclude_id=target.id) == 0:
            raise AppError("CONFLICT", "Cannot remove the last super administrator.", 409)
    target.admin_role = new_role
    db.flush()
    admin_repo.record_audit(
        db, actor_id=admin.id, action="user.role_change",
        target_type="user", target_id=target.id,
        details=audit_details("user.role_change", email=target.email),
        previous_data={"admin_role": prev},
        new_data={"admin_role": new_role},
        **(audit_ctx or {}),
    )
    return target


def change_plan(
    db: "Session", *, admin: "User", target: "User", plan_id: str,
    reason: Optional[str] = None, audit_ctx: Optional[Mapping[str, Any]] = None,
) -> "User":
    """Admin plan override (PRD §8.4). Applies plan credit limits the same way
    the billing flow does."""
    from app.services import payment_service

    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    plan = payment_service.get_plan(db, plan_id)  # raises AppError 404 if unknown
    prev = target.plan_id or "free"
    payment_service._apply_plan_to_user(db, user=target, plan=plan)
    db.flush()
    admin_repo.record_audit(
        db, actor_id=admin.id, action="user.plan_change",
        target_type="user", target_id=target.id,
        details=audit_details("user.plan_change", email=target.email),
        previous_data={"plan_id": prev},
        new_data={"plan_id": plan_id},
        reason=reason,
        **(audit_ctx or {}),
    )
    return target


def apply_user_admin_action(
    db: "Session", *, admin: "User", target: "User", action: str,
    reason: Optional[str] = None, audit_ctx: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Expanded user actions (PRD §8.4). Returns a small result dict for the
    response. Guard rails live in the pure ``validate_user_admin_action``."""
    from app.core.errors import AppError
    from app.services.admin_permissions import effective_admin_role

    AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()

    actor_role = effective_admin_role(admin.role.value, admin.admin_role)
    target_is_staff = effective_admin_role(target.role.value, target.admin_role) is not None
    try:
        validate_user_admin_action(
            action=action, actor_id=admin.id, target_id=target.id,
            target_is_staff=target_is_staff, actor_is_super=(actor_role == "super_admin"),
        )
    except ValueError as exc:
        raise AppError("CONFLICT", str(exc), 409) from exc

    prev_status = target.account_status.value
    result: dict[str, Any] = {}

    if action == "verify_email":
        target.email_verified = True
    elif action == "resend_verification":
        from app.core.security import make_email_verification_token
        from app.services.auth_service import _send_email
        token = make_email_verification_token(target.id)
        _send_email(target.email, "Verify your email",
                    f"{get_settings().app_base_url}/verify-email?token={token}")
        result["sent"] = True
    elif action == "force_password_reset":
        # Reuse the forgot-password flow (token email) + revoke sessions so
        # the user must reset before continuing.
        from app.services.auth_service import forgot_password
        forgot_password(target.email, db)
        result["revoked_sessions"] = admin_repo.revoke_all_sessions(db, target.id)
    elif action == "revoke_sessions":
        result["revoked_sessions"] = admin_repo.revoke_all_sessions(db, target.id)
    elif action in ("suspend", "ban"):
        admin_repo.set_account_status(db, target, AccountStatus.suspended)
        admin_repo.revoke_all_sessions(db, target.id)
    elif action == "restore":
        admin_repo.set_account_status(db, target, AccountStatus.active)
    elif action == "delete_account":
        admin_repo.set_account_status(db, target, AccountStatus.deleted)
        admin_repo.revoke_all_sessions(db, target.id)

    db.flush()
    admin_repo.record_audit(
        db, actor_id=admin.id, action=f"user.{action}",
        target_type="user", target_id=target.id,
        details=audit_details(f"user.{action}", email=target.email, **result),
        previous_data={"account_status": prev_status},
        new_data={"account_status": target.account_status.value},
        reason=reason,
        **(audit_ctx or {}),
    )
    result["account_status"] = target.account_status.value
    return result


def apply_project_action(
    db: "Session", *, admin: "User", project, action: str,
    reason: Optional[str] = None, hours: Optional[int] = None,
    audit_ctx: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Project moderation actions (PRD §9.5): retention, expiry, lock,
    file deletion. Storage deletion is best-effort (LocalFs has no listing)."""
    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()

    prev = {"locked": project.locked, "expires_at": _iso(project.expires_at)}
    deleted_files = 0

    if action == "extend_retention":
        project.expires_at = extend_retention_expiry(project.expires_at, hours or 0)
    elif action == "expire_now":
        project.expires_at = datetime.now(timezone.utc)
    elif action == "lock":
        project.locked = True
        if reason:
            project.moderation_note = reason
    elif action == "unlock":
        project.locked = False
    elif action == "delete_files":
        deleted_files = _delete_project_files(project)

    db.flush()
    admin_repo.record_audit(
        db, actor_id=admin.id, action=f"project.{action}",
        target_type="project", target_id=project.id,
        details=audit_details(f"project.{action}", user_id=project.user_id,
                              hours=hours, deleted_files=deleted_files or None),
        previous_data=prev,
        new_data={"locked": project.locked, "expires_at": _iso(project.expires_at)},
        reason=reason,
        **(audit_ctx or {}),
    )
    return {"deleted_files": deleted_files}


def apply_compliance_action(
    db: "Session", *, admin: "User", report, action: str,
    reason: Optional[str] = None, audit_ctx: Optional[Mapping[str, Any]] = None,
):
    """PRD §21.5 compliance actions on an abuse report + its project.

    Returns ``(report, project, target_user)``. Effects are looked up via the
    pure :func:`compliance_action_effects` map; this function only performs the
    DB mutations + audit. The caller commits.
    """
    from app.core.errors import AppError

    AccountStatus, _JobState, User, admin_repo, _proc_repo = _runtime_imports()
    effects = compliance_action_effects(action)
    if effects["requires_reason"] and not (reason and reason.strip()):
        raise AppError("VALIDATION_ERROR", f"'{action}' requires a reason.", 422)

    project = None
    if report.project_id:
        project = admin_repo.get_project(db, report.project_id)

    prev_project = None
    if project is not None and effects["project"]:
        prev_project = {k: getattr(project, k, None) for k in effects["project"]}
        for field, value in effects["project"].items():
            setattr(project, field, value)
        # A legal hold records the reason as the hold + moderation note.
        if action == "place_legal_hold" and reason:
            project.legal_hold_reason = reason
            project.moderation_note = reason

    if effects["report_status"] is not None:
        report.status = effects["report_status"]
    if reason and action == "add_note":
        report.resolution_note = reason
    report.assigned_reviewer = admin.id

    target_user = None
    if effects["account_status"] is not None and project is not None:
        target_user = db.get(User, project.user_id)
        if target_user is not None:
            # The DB enum has no dedicated "banned" state; a ban is applied as
            # the strongest available status (suspended) — the audit action name
            # ("compliance.ban_account") preserves the intent.
            status_value = effects["account_status"]
            resolved = AccountStatus.suspended if status_value == "banned" else AccountStatus(status_value)
            admin_repo.set_account_status(db, target_user, resolved)

    db.flush()
    admin_repo.record_audit(
        db, actor_id=admin.id, action=f"compliance.{action}",
        target_type="abuse_report", target_id=report.id,
        details=audit_details(f"compliance.{action}", project_id=report.project_id),
        previous_data=prev_project,
        new_data=(effects["project"] or None),
        reason=reason,
        **(audit_ctx or {}),
    )
    return report, project, target_user


def apply_storage_action(
    db: "Session", *, admin: "User", project, action: str,
    reason: Optional[str] = None, hours: Optional[int] = None,
    audit_ctx: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """PRD §18.4 storage actions on a project's files. Guards every deletion
    through :func:`storage_deletion_allowed` (§18.5). Returns a result dict.

    Supported: extend_retention, expire_now, trigger_cleanup, retry_cleanup,
    lock_compliance, verify_existence. Deletion-adjacent actions refuse when the
    project is on legal hold / locked / has an active job.
    """
    from app.core.errors import AppError

    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    prev = {"expires_at": _iso(project.expires_at), "locked": project.locked}
    result: dict[str, Any] = {}

    if action in ("trigger_cleanup", "retry_cleanup"):
        active = admin_repo.project_has_active_job(db, project.id)
        allowed, blocker = storage_deletion_allowed(
            has_active_job=active,
            legal_hold=getattr(project, "legal_hold", False),
            locked=project.locked,
            has_open_dispute=False,
        )
        if not allowed:
            raise AppError("CONFLICT", f"Deletion blocked: {blocker}.", 409)
        result["deleted_files"] = _delete_project_files(project)
        admin_repo.clear_cleanup_failed(db, project.id)
    elif action == "extend_retention":
        project.expires_at = extend_retention_expiry(project.expires_at, hours or 0)
        admin_repo.mark_retention_extended(db, project.id)
    elif action == "expire_now":
        project.expires_at = datetime.now(timezone.utc)
    elif action == "lock_compliance":
        project.locked = True
        if reason:
            project.moderation_note = reason
    elif action == "verify_existence":
        result["exists"] = _verify_project_files(project)
    else:
        raise AppError("VALIDATION_ERROR", f"Unknown storage action '{action}'.", 422)

    db.flush()
    admin_repo.record_audit(
        db, actor_id=admin.id, action=f"storage.{action}",
        target_type="project", target_id=project.id,
        details=audit_details(f"storage.{action}", hours=hours, **result),
        previous_data=prev,
        new_data={"expires_at": _iso(project.expires_at), "locked": project.locked},
        reason=reason,
        **(audit_ctx or {}),
    )
    return result


def _verify_project_files(project) -> dict[str, bool]:
    """§18.4 verify-existence: check each recorded storage key resolves."""
    from app.storage import get_storage

    storage = get_storage()
    out: dict[str, bool] = {}
    keyed = (
        ("originals", "input_storage_key"),
        ("proxies", "proxy_storage_key"),
        ("previews", "preview_storage_key"),
        ("outputs", "output_storage_key"),
        ("thumbnails", "thumbnail_storage_key"),
    )
    for bucket, attr in keyed:
        key = getattr(project, attr, None)
        if not key:
            continue
        try:
            out[bucket] = bool(storage.exists(bucket, key))
        except Exception:  # noqa: BLE001 — verification is best-effort
            out[bucket] = False
    return out


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _delete_project_files(project) -> int:
    """Best-effort removal of a project's stored artifacts. LocalFs has no
    prefix listing, so we delete the known keys recorded on the row. Keys are
    cleared so signed URLs stop resolving."""
    from app.storage import get_storage

    storage = get_storage()
    count = 0
    keyed = (
        ("originals", "input_storage_key"),
        ("proxies", "proxy_storage_key"),
        ("previews", "preview_storage_key"),
        ("outputs", "output_storage_key"),
        ("thumbnails", "thumbnail_storage_key"),
    )
    for bucket, attr in keyed:
        key = getattr(project, attr, None)
        if not key:
            continue
        try:
            storage.delete(bucket, key)
            count += 1
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass
        setattr(project, attr, None)
    return count


# ---------------------------------------------------------------------------
# Phase 6 — orchestration (models + broadcasts)
# ---------------------------------------------------------------------------


def apply_model_action(
    db: "Session", *, admin: "User", model, action: str,
    reason: Optional[str] = None, audit_ctx: Optional[Mapping[str, Any]] = None,
):
    """PRD §19.4 AI-model lifecycle action. Mutates the model row + audits.

    ``set_default``/``set_fallback`` are exclusive per model_type — promoting one
    version demotes any current holder of that flag for the same type, so there
    is exactly one default and one fallback per model family (§19.4). The caller
    commits.
    """
    from app.core.errors import AppError

    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    effects = model_action_effects(action)
    if effects["requires_reason"] and not (reason and reason.strip()):
        raise AppError("VALIDATION_ERROR", f"'{action}' requires a reason.", 422)

    prev = {"status": model.status, "is_default": model.is_default, "is_fallback": model.is_fallback}

    if effects["status"] is not None:
        model.status = effects["status"]
        if effects["status"] == "active" and model.deployment_date is None:
            model.deployment_date = datetime.now(timezone.utc)
    if effects["set_default"]:
        admin_repo.clear_model_flag(db, model_type=model.model_type, field="is_default")
        model.is_default = True
    if effects["set_fallback"]:
        admin_repo.clear_model_flag(db, model_type=model.model_type, field="is_fallback")
        model.is_fallback = True
    if action == "rollback":
        # Point runtime at the recorded previous version, if any (§19.6).
        if model.previous_version:
            fallback = admin_repo.get_model_by_name_version(db, model.name, model.previous_version)
            if fallback is not None:
                admin_repo.clear_model_flag(db, model_type=fallback.model_type, field="is_default")
                fallback.status = "active"
                fallback.is_default = True

    db.flush()
    admin_repo.record_audit(
        db, actor_id=admin.id, action=f"model.{action}",
        target_type="ai_model", target_id=model.id,
        details=audit_details(f"model.{action}", name=model.name, version=model.version),
        previous_data=prev,
        new_data={"status": model.status, "is_default": model.is_default, "is_fallback": model.is_fallback},
        reason=reason,
        **(audit_ctx or {}),
    )
    return model


def send_broadcast(
    db: "Session", *, admin: "User", kind: str, title: str, message: str,
    target: str = "all", target_plan: Optional[str] = None,
    audit_ctx: Optional[Mapping[str, Any]] = None,
):
    """PRD §23.3 broadcast to a user segment.

    Resolves the target segment to concrete users, writes one in-app
    Notification per recipient, records the Broadcast row (with the resolved
    count), and audits. The caller commits.
    """
    from app.core.errors import AppError

    _AccountStatus, _JobState, _User, admin_repo, _proc_repo = _runtime_imports()
    kind, target = validate_broadcast(kind, target)
    if not title.strip() or not message.strip():
        raise AppError("VALIDATION_ERROR", "Broadcast title and message are required.", 422)
    if target == "specific_plan" and not target_plan:
        raise AppError("VALIDATION_ERROR", "target_plan is required for a specific-plan broadcast.", 422)

    recipients = admin_repo.broadcast_recipients(db, target=target, plan=target_plan)
    admin_repo.create_notifications(db, user_ids=recipients, kind=kind, message=message)
    broadcast = admin_repo.create_broadcast(
        db, kind=kind, title=title, message=message, target=target,
        target_plan=target_plan, recipient_count=len(recipients), created_by=admin.id,
    )

    db.flush()
    admin_repo.record_audit(
        db, actor_id=admin.id, action="notifications.broadcast",
        target_type="broadcast", target_id=broadcast.id,
        details=audit_details("notifications.broadcast", kind=kind, target=target, recipients=len(recipients)),
        **(audit_ctx or {}),
    )
    return broadcast


# =====================================================================
# Phase 7 — Analytics, Exports, System Health, Admin Mgmt, Search, Secrets
# All pure (no ORM). Route/repo layer feeds these raw counts + rows.
# =====================================================================

# --- §24 Analytics (pure rate math) ---


def safe_rate(numerator: float, denominator: float, *, ndigits: int = 4) -> float:
    """Ratio in [0, 1]; 0.0 when the denominator is 0 (never divides by zero)."""
    if not denominator:
        return 0.0
    return round(max(0.0, numerator) / denominator, ndigits)


def _avg(total: float, count: float, *, ndigits: int = 2) -> float:
    """Mean that returns 0.0 for an empty population."""
    if not count:
        return 0.0
    return round(total / count, ndigits)


def product_analytics(c: Mapping[str, Any]) -> dict:
    """PRD §24.1 funnel conversion rates from raw stage counts.

    ``c`` carries integer counts for each funnel stage; missing keys read 0 so a
    partially-populated snapshot still renders. Every output is a rate in [0,1]
    except the raw totals echoed back for context.
    """
    g = lambda k: int(c.get(k, 0) or 0)  # noqa: E731
    registrations = g("registrations")
    return {
        "registrations": registrations,
        "email_verification_rate": safe_rate(g("verified_users"), registrations),
        "upload_completion_rate": safe_rate(g("uploads_completed"), g("uploads_started")),
        "analysis_completion_rate": safe_rate(g("analyses_completed"), g("analyses_started")),
        "preview_generation_rate": safe_rate(g("previews_generated"), g("projects_total")),
        "preview_to_process_rate": safe_rate(g("full_processes"), g("previews_generated")),
        "job_success_rate": safe_rate(g("jobs_succeeded"), g("jobs_total")),
        "download_completion_rate": safe_rate(g("downloads_completed"), g("downloads_started")),
        "reprocessing_rate": safe_rate(g("reprocesses"), g("jobs_total")),
        "plan_conversion_rate": safe_rate(g("paid_users"), registrations),
    }


def processing_analytics(c: Mapping[str, Any]) -> dict:
    """PRD §24.2 processing performance from aggregate totals + failure buckets.

    Failure-rate breakdowns arrive pre-grouped as ``{key: {total, failed}}`` maps
    (by model / worker / codec / resolution) and are reduced to per-key rates.
    """
    def _rates(bucket: Mapping[str, Any]) -> dict:
        out = {}
        for key, v in (bucket or {}).items():
            total = int((v or {}).get("total", 0) or 0)
            failed = int((v or {}).get("failed", 0) or 0)
            out[key] = safe_rate(failed, total)
        return out

    succeeded = int(c.get("jobs_succeeded", 0) or 0)
    return {
        "avg_processing_seconds_per_minute": _avg(c.get("processing_seconds_total", 0), c.get("video_minutes_total", 0)),
        "avg_queue_seconds": _avg(c.get("queue_seconds_total", 0), c.get("jobs_total", 0)),
        "avg_encoding_seconds": _avg(c.get("encoding_seconds_total", 0), succeeded),
        "credits_per_successful_output": _avg(c.get("credits_spent_total", 0), succeeded),
        "failure_rate_by_model": _rates(c.get("by_model", {})),
        "failure_rate_by_worker": _rates(c.get("by_worker", {})),
        "failure_rate_by_codec": _rates(c.get("by_codec", {})),
        "failure_rate_by_resolution": _rates(c.get("by_resolution", {})),
    }


# Cost assumptions (paise). Overridable per deployment; defaults are conservative
# dev-box placeholders, not production pricing.
GPU_COST_PER_HOUR_PAISE = 5000            # ₹50 / GPU-hour
STORAGE_COST_PER_GB_MONTH_PAISE = 200     # ₹2 / GB-month (matches Phase 5 estimate)


def cost_analytics(c: Mapping[str, Any]) -> dict:
    """PRD §24.4 cost estimates in paise from usage aggregates."""
    gpu_seconds = float(c.get("gpu_seconds_total", 0) or 0)
    completed = int(c.get("jobs_completed", 0) or 0)
    users = int(c.get("active_users", 0) or 0)
    projects = int(c.get("projects_total", 0) or 0)
    minutes = float(c.get("video_minutes_total", 0) or 0)
    storage_gb = float(c.get("storage_bytes_total", 0) or 0) / (1024 ** 3)

    gpu_cost = (gpu_seconds / 3600.0) * GPU_COST_PER_HOUR_PAISE
    storage_cost = storage_gb * STORAGE_COST_PER_GB_MONTH_PAISE
    return {
        "gpu_cost_per_completed_job_paise": int(_avg(gpu_cost, completed, ndigits=0)),
        "storage_cost_per_user_paise": int(_avg(storage_cost, users, ndigits=0)),
        "storage_cost_per_project_paise": int(_avg(storage_cost, projects, ndigits=0)),
        "infra_cost_per_processed_minute_paise": int(_avg(gpu_cost + storage_cost, minutes, ndigits=0)),
        "total_gpu_cost_paise": int(round(gpu_cost)),
        "total_storage_cost_paise": int(round(storage_cost)),
    }


# --- §24.5 Exports (pure serialization) ---

EXPORT_FORMATS = ("csv", "json")


def filter_export_rows(rows: Iterable[Mapping[str, Any]], allowed: Iterable[str]) -> list[dict]:
    """Project each row down to ``allowed`` columns (PRD §24.5 — hide restricted
    fields). Columns absent from a row are emitted as empty so the CSV stays
    rectangular."""
    cols = list(allowed)
    return [{col: row.get(col, "") for col in cols} for row in rows]


def to_csv(rows: Iterable[Mapping[str, Any]], columns: Iterable[str]) -> str:
    """RFC-4180 CSV with a header row. Values are stringified; quotes/newlines/
    commas are escaped by doubling quotes and wrapping. Pure — no csv module I/O
    handles so the output is deterministic across platforms (``\\r\\n`` line ends)."""
    cols = list(columns)

    def esc(value: Any) -> str:
        s = "" if value is None else str(value)
        if any(ch in s for ch in (",", '"', "\n", "\r")):
            return '"' + s.replace('"', '""') + '"'
        return s

    lines = [",".join(esc(col) for col in cols)]
    for row in rows:
        lines.append(",".join(esc(row.get(col, "")) for col in cols))
    return "\r\n".join(lines)


def validate_export_format(fmt: str) -> str:
    from app.core.errors import AppError

    fmt = (fmt or "csv").lower()
    if fmt not in EXPORT_FORMATS:
        raise AppError("VALIDATION_ERROR", f"Unsupported export format '{fmt}'.", 422)
    return fmt


# --- §25 System Health (pure) ---

# Services the health board reports on (PRD §25.1).
SERVICE_NAMES = (
    "frontend", "backend", "postgres", "redis", "celery",
    "object_storage", "gpu_workers", "razorpay", "email", "signed_url",
)

# Metric evaluation thresholds: (warn_at, critical_at). Higher-is-worse.
_HEALTH_THRESHOLDS = {
    "api_response_ms": (500, 1500),
    "api_error_rate": (0.02, 0.05),
    "db_connections": (80, 95),
    "db_latency_ms": (50, 200),
    "redis_memory_mb": (512, 900),
    "queue_depth": (50, 200),
    "worker_heartbeat_failures": (1, 3),
    "storage_io_failures": (1, 5),
    "webhook_failures": (1, 5),
    "email_failures": (1, 5),
}

INCIDENT_SEVERITIES = ("info", "minor", "major", "critical")
INCIDENT_STATUSES = ("open", "monitoring", "resolved")
INCIDENT_ACTIONS = ("acknowledge", "silence", "add_note", "resolve", "reopen")


def service_status_list(checks: Mapping[str, Optional[bool]]) -> list[dict]:
    """Map raw up/down/unknown checks to the canonical service list (PRD §25.1).

    ``True`` → operational, ``False`` → down, ``None``/missing → unknown. Order
    follows :data:`SERVICE_NAMES` so the board is stable."""
    out = []
    for name in SERVICE_NAMES:
        raw = checks.get(name)
        status = "operational" if raw is True else "down" if raw is False else "unknown"
        out.append({"name": name, "status": status})
    return out


def health_status_for(metric: str, value: Optional[float]) -> str:
    """Classify one metric as ok / warn / critical (PRD §25.2). Unknown metric or
    ``None`` value → ``unknown`` (never raises — the board must always render)."""
    if value is None or metric not in _HEALTH_THRESHOLDS:
        return "unknown"
    warn, crit = _HEALTH_THRESHOLDS[metric]
    if value >= crit:
        return "critical"
    if value >= warn:
        return "warn"
    return "ok"


def evaluate_health_metrics(metrics: Mapping[str, Any]) -> list[dict]:
    """Per-metric {metric, value, status} rows over the known threshold set."""
    out = []
    for metric in _HEALTH_THRESHOLDS:
        value = metrics.get(metric)
        out.append({"metric": metric, "value": value, "status": health_status_for(metric, value)})
    return out


def overall_health(service_rows: Iterable[Mapping[str, Any]], metric_rows: Iterable[Mapping[str, Any]]) -> str:
    """Roll services + metrics into one banner state (worst wins)."""
    statuses = {r.get("status") for r in service_rows} | {r.get("status") for r in metric_rows}
    if "down" in statuses or "critical" in statuses:
        return "critical"
    if "warn" in statuses or "unknown" in statuses:
        return "degraded"
    return "operational"


def validate_incident_action(action: str) -> str:
    from app.core.errors import AppError

    if action not in INCIDENT_ACTIONS:
        raise AppError("VALIDATION_ERROR", f"Unknown incident action '{action}'.", 422)
    return action


def incident_action_effects(action: str) -> dict:
    """Action → mutation intent for an incident row (PRD §25.4).

    ``requires_note`` gates the note-capture on the route; ``status`` is the new
    incident status (None = unchanged, e.g. a pure silence/ack)."""
    action = validate_incident_action(action)
    return {
        "acknowledge": {"status": "monitoring", "requires_note": False, "silence": False},
        "silence": {"status": None, "requires_note": False, "silence": True},
        "add_note": {"status": None, "requires_note": True, "silence": False},
        "resolve": {"status": "resolved", "requires_note": True, "silence": False},
        "reopen": {"status": "open", "requires_note": False, "silence": False},
    }[action]


# --- §28 Administrator management (pure) ---

ADMIN_MGMT_ACTIONS = (
    "assign_role", "change_role", "suspend", "reactivate",
    "revoke_sessions", "require_password_reset", "require_mfa", "remove",
)
# Actions that must never be applied to yourself (lock-out / privilege-escalation
# guards, PRD §28.3).
_ADMIN_SELF_BLOCKED = frozenset({"suspend", "remove", "change_role", "assign_role"})
_ADMIN_DESTRUCTIVE = frozenset({"suspend", "remove"})


def validate_admin_mgmt_action(
    action: str, *, actor_id: str, target_id: str, target_admin_role: Optional[str],
    new_role: Optional[str] = None, reason: Optional[str] = None,
) -> None:
    """Guard rails for administrator-management actions (PRD §28.2/§28.3).

    * unknown action → 422
    * self-targeting for status/role changes → 422 (can't lock yourself out)
    * role changes must name a known role
    * demoting/removing the last active super_admin is blocked at the repo layer
      (needs a live count); here we enforce the shape only
    * destructive actions require a reason
    """
    if action not in ADMIN_MGMT_ACTIONS:
        raise AppError("VALIDATION_ERROR", f"Unknown administrator action '{action}'.", 422)
    if actor_id == target_id and action in _ADMIN_SELF_BLOCKED:
        raise AppError("VALIDATION_ERROR", "You cannot apply this action to your own account.", 422)
    if action in ("assign_role", "change_role"):
        if new_role not in PERMISSIONS:
            raise AppError("VALIDATION_ERROR", f"Unknown admin role '{new_role}'.", 422)
    if action in _ADMIN_DESTRUCTIVE and not (reason or "").strip():
        raise AppError("VALIDATION_ERROR", "This action requires a reason.", 422)


# --- §29 Global search (pure classifier) ---

SEARCH_ENTITY_TYPES = (
    "user", "project", "job", "payment", "razorpay_payment",
    "subscription", "promo", "worker", "abuse_report",
)

_UUID_RE = None  # compiled lazily below to avoid importing re at module import cost


def classify_search_query(q: str) -> list[str]:
    """Guess which entity types a search token could match (PRD §29).

    Returns candidate entity-type names (subset of :data:`SEARCH_ENTITY_TYPES`),
    most-specific first, so the repo layer only queries relevant tables. A bare /
    ambiguous token falls back to the broad set (user email/id, promo, worker).
    """
    import re

    token = (q or "").strip()
    if not token:
        return []

    hits: list[str] = []

    def add(name: str) -> None:
        if name not in hits:
            hits.append(name)

    # Gateway IDs carry Razorpay's typed prefixes.
    if re.match(r"^pay_[A-Za-z0-9]+$", token):
        add("razorpay_payment"); add("payment")
    elif re.match(r"^order_[A-Za-z0-9]+$", token):
        add("payment")
    elif re.match(r"^sub_[A-Za-z0-9]+$", token):
        add("subscription")
    elif "@" in token:
        add("user")
    elif re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", token):
        # A bare UUID could be any of our String(36) PKs — probe the common ones.
        for name in ("user", "project", "job", "payment", "subscription", "abuse_report"):
            add(name)
    elif re.match(r"^[A-Z0-9][A-Z0-9_-]{2,}$", token):
        # ALL-CAPS alnum → a promo code (also try worker names, which are slugs).
        add("promo"); add("worker")
    else:
        # Free text: names/emails/worker slugs.
        add("user"); add("worker")
    return hits


# --- §26.7 Secret handling (pure — never returns a full secret) ---

# The env/config-backed secrets the panel may *describe* but never reveal.
SECRET_KEYS = (
    "jwt_secret",
    "razorpay_key_id",
    "razorpay_key_secret",
    "razorpay_webhook_secret",
    "storage_access_key",
    "storage_secret_key",
    "database_url",
    "email_password",
)
# razorpay_key_id is a public identifier, not a secret — safe to show in full.
_PUBLIC_SECRET_KEYS = frozenset({"razorpay_key_id"})


def describe_secret(name: str, raw_value: Optional[str], *, updated_at: Optional[str] = None) -> dict:
    """Non-revealing descriptor for a secret (PRD §26.7).

    Shows only: configured-or-missing, last-four characters (for private
    secrets), and last-updated date. The raw value NEVER leaves this function.
    ``database_url`` is treated as fully-private (even the host is withheld
    beyond the last four)."""
    value = raw_value or ""
    configured = bool(value.strip())
    public = name in _PUBLIC_SECRET_KEYS
    last_four = value[-4:] if (configured and len(value) >= 4) else ""
    return {
        "name": name,
        "configured": configured,
        "public": public,
        "value": value if (public and configured) else None,
        "last_four": last_four,
        "updated_at": updated_at,
    }


__all__ = [
    "config_value_to_str",
    "config_value_from_str",
    "build_config",
    "is_worker_online",
    "fuse_workers",
    "audit_details",
    "retention_deltas",
    "is_brittle_region",
    "get_overview",
    "get_workers",
    "apply_user_action",
    "apply_job_action",
    "apply_abuse_action",
    "ALL_CONFIG_KEYS",
    # Phases 1+2
    "paginate",
    "page_envelope",
    "build_credit_txn",
    "validate_user_admin_action",
    "extend_retention_expiry",
    "overview_extras",
    "job_stage_timeline",
    "is_terminal_job_state",
    "build_audit_context",
    "get_user_detail",
    "adjust_credits",
    "change_admin_role",
    "change_plan",
    "apply_user_admin_action",
    "apply_project_action",
    "CREDIT_SOURCES",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    # Phase 4 — billing (pure)
    "PAYMENT_STATUSES",
    "SUBSCRIPTION_STATUSES",
    "DISCOUNT_TYPES",
    "BILLING_INTERVALS",
    "REFUND_SUPER_ADMIN_THRESHOLD_INR",
    "mask_secret",
    "refund_requires_approval",
    "validate_refund",
    "refund_status_after",
    "billing_overview",
    "promo_remaining_uses",
    "validate_plan_fields",
    "validate_promo_fields",
    "credit_dashboard",
    "subscription_display_status",
    "mask_webhook_payload",
    "apply_subscription_action",
    # Phase 5 — storage & compliance (pure)
    "STORAGE_BUCKETS",
    "ABUSE_STATUSES",
    "ABUSE_SEVERITIES",
    "COMPLIANCE_ACTIONS",
    "storage_overview",
    "storage_deletion_allowed",
    "retention_bucket",
    "validate_abuse_severity",
    "compliance_action_effects",
    "compliance_overview",
    # Phase 5 — orchestration
    "apply_compliance_action",
    "apply_storage_action",
    # Phase 6 — models/presets/flags/notifications/maintenance (pure)
    "MODEL_TYPES",
    "MODEL_STATUSES",
    "MODEL_ACTIONS",
    "ROLLOUT_STRATEGIES",
    "NOTIFICATION_TEMPLATE_KEYS",
    "BROADCAST_KINDS",
    "BROADCAST_TARGETS",
    "FEATURE_FLAG_KEYS",
    "MAINTENANCE_SETTING_KEY",
    "MAINTENANCE_DEFAULTS",
    "validate_model_type",
    "validate_model_action",
    "model_action_effects",
    "validate_rollout",
    "validate_preset_fields",
    "merge_feature_flags",
    "normalise_maintenance",
    "validate_broadcast",
    "render_template_preview",
    # Phase 6 — orchestration
    "apply_model_action",
    "send_broadcast",
    # Phase 7 — analytics / exports / health / admin-mgmt / search / secrets (pure)
    "safe_rate",
    "product_analytics",
    "processing_analytics",
    "cost_analytics",
    "GPU_COST_PER_HOUR_PAISE",
    "STORAGE_COST_PER_GB_MONTH_PAISE",
    "EXPORT_FORMATS",
    "filter_export_rows",
    "to_csv",
    "validate_export_format",
    "SERVICE_NAMES",
    "INCIDENT_SEVERITIES",
    "INCIDENT_STATUSES",
    "INCIDENT_ACTIONS",
    "service_status_list",
    "health_status_for",
    "evaluate_health_metrics",
    "overall_health",
    "validate_incident_action",
    "incident_action_effects",
    "ADMIN_MGMT_ACTIONS",
    "validate_admin_mgmt_action",
    "SEARCH_ENTITY_TYPES",
    "classify_search_query",
    "SECRET_KEYS",
    "describe_secret",
]
