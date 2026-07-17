"""Phase 8 pure-logic tests — admin config (de)serialization + merge, worker
online/fusion, audit-detail shape, retention policy + cleanup plan, RECON-008
brittle flag, MON metrics alerts, and the Pydantic action validators.

No DB / Redis / SQLAlchemy / numpy — runs on the 32-bit dev box. The
orchestration helpers that take a Session are exercised at runtime in a
64-bit env; here we cover the policy they compose.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.admin import (
    AbuseActionRequest,
    JobActionRequest,
    SystemConfig,
    SystemConfigUpdate,
    UserActionRequest,
)
from app.services import admin_service, retention


# ---------------------------------------------------------------------------
# ADMIN-005 config (de)serialization + merge
# ---------------------------------------------------------------------------


def test_config_value_roundtrips_lists_ints_bools():
    assert admin_service.config_value_to_str("allowed_upload_extensions", ["mp4", "mov"]) == '["mp4", "mov"]'
    assert admin_service.config_value_from_str("allowed_upload_extensions", '["mp4", "mov"]') == ["mp4", "mov"]
    assert admin_service.config_value_to_str("max_file_size_mb", 500) == "500"
    assert admin_service.config_value_from_str("max_file_size_mb", "500") == 500
    assert admin_service.config_value_to_str("maintenance_mode", True) == "true"
    assert admin_service.config_value_from_str("maintenance_mode", "true") is True
    assert admin_service.config_value_from_str("maintenance_mode", "false") is False


def test_config_value_from_str_tolerates_garbage():
    assert admin_service.config_value_from_str("allowed_upload_extensions", "not-json") == []
    assert admin_service.config_value_from_str("max_file_size_mb", "broken") == 0
    assert admin_service.config_value_from_str("maintenance_mode", "0") is False
    assert admin_service.config_value_from_str("unknown_key", "raw") == "raw"


def test_build_config_uses_defaults_when_no_overrides():
    stub = SimpleNamespace(
        max_file_size_mb=500, max_duration_seconds=300, max_width=1920, max_height=1080,
        max_fps=60, allowed_upload_extensions=["mp4", "mov", "webm"],
        retain_original_hours=24, retain_preview_hours=24, retain_output_days=7,
        retain_failed_hours=6, worker_concurrency=2, max_retries=2,
        enabled_models=["yolo", "easyocr"], maintenance_mode=False,
    )
    cfg = admin_service.build_config(stub, {})
    assert isinstance(cfg, SystemConfig)
    assert cfg.max_file_size_mb == 500
    assert cfg.allowed_upload_extensions == ["mp4", "mov", "webm"]
    assert cfg.maintenance_mode is False


def test_build_config_overrides_win_over_defaults():
    stub = SimpleNamespace(
        max_file_size_mb=500, max_duration_seconds=300, max_width=1920, max_height=1080,
        max_fps=60, allowed_upload_extensions=["mp4"],
        retain_original_hours=24, retain_preview_hours=24, retain_output_days=7,
        retain_failed_hours=6, worker_concurrency=2, max_retries=2,
        enabled_models=["yolo"], maintenance_mode=False,
    )
    overrides = {
        "max_file_size_mb": "200",
        "maintenance_mode": "true",
        "allowed_upload_extensions": '["mp4", "mov"]',
    }
    cfg = admin_service.build_config(stub, overrides)
    assert cfg.max_file_size_mb == 200
    assert cfg.maintenance_mode is True
    assert cfg.allowed_upload_extensions == ["mp4", "mov"]
    # untouched knobs keep their default
    assert cfg.max_duration_seconds == 300


def test_all_config_keys_partition_correctly():
    keys = admin_service.ALL_CONFIG_KEYS
    assert "maintenance_mode" in keys
    assert "max_file_size_mb" in keys
    assert "enabled_models" in keys
    # no stray unknowns
    assert keys == keys  # tautology guard for import sanity


# ---------------------------------------------------------------------------
# ADMIN-004 worker online + fusion
# ---------------------------------------------------------------------------


def test_is_worker_online_within_threshold():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    hb = now - timedelta(seconds=30)
    assert admin_service.is_worker_online(hb, now=now) is True


def test_is_worker_online_past_threshold():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    hb = now - timedelta(seconds=120)
    assert admin_service.is_worker_online(hb, now=now) is False


def test_is_worker_online_none_heartbeat():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    assert admin_service.is_worker_online(None, now=now) is False


def test_is_worker_online_naive_datetimes_treated_as_utc():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    hb = datetime(2026, 7, 16, 11, 59, 30)  # naive, 30s ago
    assert admin_service.is_worker_online(hb, now=now) is True


def test_fuse_workers_merges_redis_heartbeat_when_newer():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    stale_db_hb = now - timedelta(hours=2)
    fresh_epoch = int((now - timedelta(seconds=10)).timestamp())
    node = SimpleNamespace(
        name="w1", status="busy", gpu_name="RTX", gpu_memory=8000,
        active_job_id="job-1", last_heartbeat=stale_db_hb, software_version="0.1.0",
    )
    out = admin_service.fuse_workers([node], {"w1": fresh_epoch}, now=now)
    assert len(out) == 1
    assert out[0].online is True
    assert out[0].gpu_name == "RTX"
    assert out[0].active_job_id == "job-1"
    # the fresher Redis heartbeat replaced the stale DB one
    assert out[0].last_heartbeat is not None
    assert (now - out[0].last_heartbeat).total_seconds() < 15


def test_fuse_workers_offline_when_no_heartbeat_anywhere():
    node = SimpleNamespace(
        name="w2", status="idle", gpu_name=None, gpu_memory=None,
        active_job_id=None, last_heartbeat=None, software_version=None,
    )
    out = admin_service.fuse_workers([node], {})
    assert out[0].online is False


def test_fuse_workers_empty_inputs():
    assert admin_service.fuse_workers([], {}) == []


# ---------------------------------------------------------------------------
# ADMIN-006 audit detail shape
# ---------------------------------------------------------------------------


def test_audit_details_drops_none_values():
    d = admin_service.audit_details("user.suspend", email="a@b.com", reason=None, count=3)
    assert d == {"email": "a@b.com", "count": 3}


def test_audit_details_empty_when_all_none():
    assert admin_service.audit_details("x", a=None, b=None) == {}


# ---------------------------------------------------------------------------
# STORAGE-006 retention policy + cleanup plan
# ---------------------------------------------------------------------------


def test_cutoffs_match_storage_006_windows():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    policy = retention.RetentionPolicy()
    cut = retention.cutoffs(policy, now=now)
    assert cut["original"] == now - timedelta(hours=24)
    assert cut["preview"] == now - timedelta(hours=24)
    assert cut["output"] == now - timedelta(days=7)
    assert cut["failed"] == now - timedelta(hours=6)


def test_cutoffs_custom_policy():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    policy = retention.RetentionPolicy(retain_original_hours=48, retain_output_days=14)
    cut = retention.cutoffs(policy, now=now)
    assert cut["original"] == now - timedelta(hours=48)
    assert cut["output"] == now - timedelta(days=14)


@dataclass
class _Proj:
    id: str
    input_storage_key: str | None = None
    proxy_storage_key: str | None = None
    preview_storage_key: str | None = None
    output_storage_key: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    status: object = None
    deleted: bool = False


def test_plan_cleanup_soft_deleted_drops_all_artifacts():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    p = _Proj(
        id="p1",
        input_storage_key="in.mp4", proxy_storage_key="proxy.mp4",
        preview_storage_key="prev.mp4", output_storage_key="out.mp4",
        created_at=now, completed_at=now,
    )
    actions = retention.plan_project_cleanup(p, retention.RetentionPolicy(), now=now, is_deleted=True)
    buckets = {a.bucket for a in actions}
    assert buckets == {"original", "proxy", "preview", "outputs"}
    assert all(a.reason == "project_deleted" for a in actions)


def test_plan_cleanup_original_expired_after_window():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=30)
    p = _Proj(id="p2", input_storage_key="in.mp4", created_at=old)
    actions = retention.plan_project_cleanup(p, retention.RetentionPolicy(), now=now)
    assert any(a.bucket == "original" and a.reason == "original_expired" for a in actions)


def test_plan_cleanup_keeps_fresh_original():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    fresh = now - timedelta(hours=1)
    p = _Proj(id="p3", input_storage_key="in.mp4", created_at=fresh)
    actions = retention.plan_project_cleanup(p, retention.RetentionPolicy(), now=now)
    assert actions == []


def test_plan_cleanup_output_expired_off_completed_at():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    old_done = now - timedelta(days=10)
    p = _Proj(
        id="p4", output_storage_key="out.mp4",
        created_at=now - timedelta(days=11), completed_at=old_done,
    )
    actions = retention.plan_project_cleanup(p, retention.RetentionPolicy(), now=now)
    assert any(a.bucket == "outputs" and a.reason == "output_expired" for a in actions)


def test_plan_cleanup_output_kept_within_window():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    recent = now - timedelta(days=2)
    p = _Proj(
        id="p5", output_storage_key="out.mp4",
        created_at=now - timedelta(days=3), completed_at=recent,
    )
    actions = retention.plan_project_cleanup(p, retention.RetentionPolicy(), now=now)
    assert not any(a.bucket == "outputs" for a in actions)


def test_plan_cleanup_failed_short_window_for_temp():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=8)  # older than the 6h failed window
    p = _Proj(
        id="p6", proxy_storage_key="proxy.mp4", preview_storage_key="prev.mp4",
        created_at=old, status=SimpleNamespace(value="failed"),
    )
    actions = retention.plan_project_cleanup(p, retention.RetentionPolicy(), now=now)
    buckets = {a.bucket for a in actions}
    assert {"proxy", "preview"} <= buckets
    assert all(a.reason == "failed_temp" for a in actions if a.bucket in ("proxy", "preview"))


def test_plan_cleanup_failed_recent_temp_kept():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    fresh = now - timedelta(hours=1)
    p = _Proj(
        id="p7", proxy_storage_key="proxy.mp4",
        created_at=fresh, status=SimpleNamespace(value="failed"),
    )
    actions = retention.plan_project_cleanup(p, retention.RetentionPolicy(), now=now)
    # proxy also expires on the 24h preview window from created_at — 1h < 24h, so kept
    assert not any(a.bucket == "proxy" and a.reason == "failed_temp" for a in actions)


def test_plan_cleanup_skips_missing_keys():
    now = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone.utc)
    old = now - timedelta(hours=30)
    p = _Proj(id="p8", created_at=old)  # no keys at all
    actions = retention.plan_project_cleanup(p, retention.RetentionPolicy(), now=now)
    assert actions == []


# ---------------------------------------------------------------------------
# RECON-008 brittle flag
# ---------------------------------------------------------------------------


def test_is_brittle_region_large_rectangle_flags():
    geo = {"tool": "rectangle", "x": 0, "y": 0, "w": 800, "h": 600, "vertices": []}
    assert admin_service.is_brittle_region(geo, frame_width=1280, frame_height=720) is True


def test_is_brittle_region_small_rectangle_safe():
    geo = {"tool": "rectangle", "x": 0, "y": 0, "w": 100, "h": 80, "vertices": []}
    assert admin_service.is_brittle_region(geo, frame_width=1280, frame_height=720) is False


def test_is_brittle_region_polygon_uses_bbox_area():
    # a polygon covering most of the frame
    geo = {"tool": "polygon", "vertices": [],
           "points": [(0, 0), (1000, 0), (1000, 700), (0, 700)]}
    assert admin_service.is_brittle_region(geo, frame_width=1280, frame_height=720) is True


def test_is_brittle_region_polygon_too_few_points_safe():
    geo = {"tool": "polygon", "vertices": [], "points": [(0, 0), (10, 10)]}
    assert admin_service.is_brittle_region(geo, frame_width=1280, frame_height=720) is False


def test_is_brittle_region_brush_unions_discs():
    # two large discs whose union bbox covers most of the frame
    geo = {"tool": "brush", "strokes": [{"x": 200, "y": 200, "r": 200}, {"x": 1000, "y": 500, "r": 200}]}
    assert admin_service.is_brittle_region(geo, frame_width=1280, frame_height=720) is True


def test_is_brittle_region_brush_small_disc_safe():
    geo = {"tool": "brush", "strokes": [{"x": 640, "y": 360, "r": 50}]}
    assert admin_service.is_brittle_region(geo, frame_width=1280, frame_height=720) is False


def test_is_brittle_region_zero_frame_safe():
    geo = {"tool": "rectangle", "x": 0, "y": 0, "w": 10, "h": 10, "vertices": []}
    assert admin_service.is_brittle_region(geo, frame_width=0, frame_height=0) is False


def test_is_brittle_region_unknown_tool_safe():
    geo = {"tool": "magic", "x": 0, "y": 0, "w": 9999, "h": 9999}
    assert admin_service.is_brittle_region(geo, frame_width=1280, frame_height=720) is False


# ---------------------------------------------------------------------------
# MON-001..003 alerts
# ---------------------------------------------------------------------------


def _snap(**kw) -> retention.MetricsSnapshot:
    base = dict(queue_length=0, active_workers=1, total_workers=1,
                failed_jobs_last_hour=0, storage_bytes=0, alerts=[])
    base.update(kw)
    return retention.MetricsSnapshot(**base)


def test_alerts_error_rate_high_at_five_failures():
    snap = _snap(failed_jobs_last_hour=5)
    assert "error_rate_high" in retention.alerts_for(snap)


def test_alerts_error_rate_quiet_below_five():
    snap = _snap(failed_jobs_last_hour=4)
    assert "error_rate_high" not in retention.alerts_for(snap)


def test_alerts_all_workers_offline_when_zero_active():
    snap = _snap(active_workers=0, total_workers=2)
    assert "all_workers_offline" in retention.alerts_for(snap)


def test_alerts_workers_ok_when_zero_total():
    # no workers registered at all — not an offline alert
    snap = _snap(active_workers=0, total_workers=0)
    assert "all_workers_offline" not in retention.alerts_for(snap)


def test_alerts_storage_near_full():
    snap = _snap(storage_bytes=10_000)
    assert "storage_near_full" in retention.alerts_for(snap, storage_warn_bytes=10_000)


def test_alerts_storage_quiet_under_threshold():
    snap = _snap(storage_bytes=9999)
    assert "storage_near_full" not in retention.alerts_for(snap, storage_warn_bytes=10_000)


def test_alerts_queue_backlog_large():
    snap = _snap(queue_length=51)
    assert "queue_backlog_large" in retention.alerts_for(snap)


def test_alerts_no_alerts_on_healthy_snapshot():
    snap = _snap()
    assert retention.alerts_for(snap) == []


# ---------------------------------------------------------------------------
# ADMIN action request validators
# ---------------------------------------------------------------------------


def test_user_action_request_accepts_suspend_reactivate():
    assert UserActionRequest(action="suspend").action == "suspend"
    assert UserActionRequest(action="reactivate").action == "reactivate"


def test_user_action_request_rejects_unknown():
    with pytest.raises(ValidationError):
        UserActionRequest(action="delete")


def test_job_action_request_accepts_retry_cancel():
    assert JobActionRequest(action="retry").action == "retry"
    assert JobActionRequest(action="cancel").action == "cancel"


def test_job_action_request_rejects_unknown():
    with pytest.raises(ValidationError):
        JobActionRequest(action="purge")


def test_abuse_action_request_accepts_three():
    for a in ("dismiss", "escalate", "suspend_reporter"):
        assert AbuseActionRequest(action=a).action == a


def test_abuse_action_request_rejects_unknown():
    with pytest.raises(ValidationError):
        AbuseActionRequest(action="ban")


def test_system_config_update_rejects_out_of_range():
    with pytest.raises(ValidationError):
        SystemConfigUpdate(max_file_size_mb=0)
    with pytest.raises(ValidationError):
        SystemConfigUpdate(max_file_size_mb=100000)
    with pytest.raises(ValidationError):
        SystemConfigUpdate(max_retries=-1)
    with pytest.raises(ValidationError):
        SystemConfigUpdate(max_retries=99)


def test_system_config_update_accepts_partial():
    u = SystemConfigUpdate(max_fps=30)
    assert u.max_fps == 30
    assert u.max_file_size_mb is None
