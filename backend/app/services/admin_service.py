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
from app.schemas.admin import SystemConfig, WorkerInfo

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


# --- STORAGE-006: retention policy (pure) ---


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


# --- RECON-008: brittle-flag decision (pure) ---


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
    job.status = JobState.created
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
]
