"""Retention + cleanup policy (SRS STORAGE-006, MON-001..003).

Pure policy helpers — no ORM imports — so the cutoff math and the
"which artifacts are expired" decision run on the 32-bit dev box and are
unit-tested directly. The :mod:`workers.tasks.maintenance` task calls these
with real rows at runtime.

STORAGE-006 windows:
    original  24h   — the user's source file, kept for re-download/re-process
    preview   24h   — the proxy + preview clip
    output     7d   — the cleaned result
    failed     6h   — temp artifacts from a failed job
    frames  immediate — deleted as soon as encode finishes (no cutoff here)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional


@dataclass(frozen=True)
class RetentionPolicy:
    retain_original_hours: int = 24
    retain_preview_hours: int = 24
    retain_output_days: int = 7
    retain_failed_hours: int = 6


@dataclass(frozen=True)
class CleanupAction:
    """One artifact to delete. ``bucket`` is the storage bucket name
    (originals | proxies | previews | outputs); ``key`` is the storage key."""

    project_id: str
    bucket: str
    key: str
    reason: str  # original_expired | preview_expired | output_expired | failed_temp | project_deleted


def _utc(now: Optional[datetime]) -> datetime:
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return ref


def cutoffs(policy: RetentionPolicy, *, now: Optional[datetime] = None) -> dict[str, datetime]:
    """Per-class cutoff timestamps. An artifact older than its cutoff is
    eligible for deletion. Mirrors :func:`admin_service.retention_deltas` but
    lives here so the maintenance task has a single dependency."""
    ref = _utc(now)
    return {
        "original": ref - timedelta(hours=policy.retain_original_hours),
        "preview": ref - timedelta(hours=policy.retain_preview_hours),
        "output": ref - timedelta(days=policy.retain_output_days),
        "failed": ref - timedelta(hours=policy.retain_failed_hours),
    }


def plan_project_cleanup(
    project,
    policy: RetentionPolicy,
    *,
    now: Optional[datetime] = None,
    is_deleted: bool = False,
) -> list[CleanupAction]:
    """Decide which storage keys for a single project should be deleted.

    ``project`` is any object exposing the storage-key attributes + the
    created/completed timestamps + status. Kept duck-typed so a plain
    dataclass / dict-wrapper can stand in for the ORM row in tests.

    Rules:
      * A project under legal hold is never cleaned (the flag "blocks retention
        cleanup and file deletion" — PRD §18), even if soft-deleted.
      * If the project is soft-deleted, drop every artifact (all buckets).
      * original  + proxy  + preview: expired after their window from created_at.
      * output: expired after its window from completed_at (only if completed).
      * failed: the project's temp artifacts (proxy/preview) expire on the
        short failed window once the project is in the failed state.
      * originals/proxies are kept while a job could still need them: projects
        actively processing (or queued/awaiting review) keep their source.
    """
    ref = _utc(now)
    cut = cutoffs(policy, now=ref)
    actions: list[CleanupAction] = []
    pid = _attr(project, "id", "")

    if _attr(project, "legal_hold", False):
        return actions

    def _older(ts_attr: str, cutoff: datetime) -> bool:
        ts = _attr(project, ts_attr, None)
        if ts is None:
            return False
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts < cutoff

    if is_deleted or _attr(project, "deleted", False):
        for bucket, key_attr in (
            ("originals", "input_storage_key"),
            ("proxies", "proxy_storage_key"),
            ("previews", "preview_storage_key"),
            ("outputs", "output_storage_key"),
        ):
            k = _attr(project, key_attr, None)
            if k:
                actions.append(CleanupAction(pid, bucket, k, "project_deleted"))
        return actions

    status = _attr(project, "status", None)
    status_val = status.value if hasattr(status, "value") else status

    # A queued/active/awaiting-approval project still needs its source: the
    # worker downloads the original at execution time, so expiring it here
    # would fail the in-flight job ("never in-flight ones" — module contract).
    _ACTIVE = {
        "processing_queued", "processing", "encoding", "analyzing",
        "preview_queued", "preview_processing", "preview_ready", "awaiting_review",
    }
    source_in_use = status_val in _ACTIVE

    # original + proxy + preview expire off created_at
    for bucket, key_attr, reason in (
        ("originals", "input_storage_key", "original_expired"),
        ("proxies", "proxy_storage_key", "preview_expired"),
        ("previews", "preview_storage_key", "preview_expired"),
    ):
        if source_in_use and bucket in ("originals", "proxies"):
            continue
        k = _attr(project, key_attr, None)
        if k and _older("created_at", cut["original" if bucket == "originals" else "preview"]):
            actions.append(CleanupAction(pid, bucket, k, reason))

    # output expires off completed_at
    out_key = _attr(project, "output_storage_key", None)
    if out_key and _older("completed_at", cut["output"]):
        actions.append(CleanupAction(pid, "outputs", out_key, "output_expired"))

    # failed-job temp artifacts expire on the short failed window
    if status_val == "failed":
        failed_cut = cut["failed"]
        for bucket, key_attr in (("proxies", "proxy_storage_key"), ("previews", "preview_storage_key")):
            k = _attr(project, key_attr, None)
            if k and _older("created_at", failed_cut):
                actions.append(CleanupAction(pid, bucket, k, "failed_temp"))
    return actions


def _attr(obj, name, default):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


# --- MON-001..003 metrics (pure) ---


@dataclass(frozen=True)
class MetricsSnapshot:
    queue_length: int
    active_workers: int
    total_workers: int
    failed_jobs_last_hour: int
    storage_bytes: int
    alerts: list[str]


def alerts_for(snapshot: MetricsSnapshot, *, storage_warn_bytes: int = 0) -> list[str]:
    """MON-001/002/003 alert rules over a snapshot. Pure so thresholds are
    unit-testable. Returns the list of raised alert strings."""
    out: list[str] = []
    if snapshot.failed_jobs_last_hour >= 5:
        out.append("error_rate_high")
    if snapshot.active_workers == 0 and snapshot.total_workers > 0:
        out.append("all_workers_offline")
    if storage_warn_bytes and snapshot.storage_bytes >= storage_warn_bytes:
        out.append("storage_near_full")
    if snapshot.queue_length > 50:
        out.append("queue_backlog_large")
    return out


__all__ = [
    "RetentionPolicy",
    "CleanupAction",
    "cutoffs",
    "plan_project_cleanup",
    "MetricsSnapshot",
    "alerts_for",
]
