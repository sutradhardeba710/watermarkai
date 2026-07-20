"""Admin Panel Phase 7 pure-logic tests — analytics, exports, system health,
administrator management, global search, secret handling
(PRD §24, §24.5, §25, §26.7, §28, §29).

No DB / SQLAlchemy — every function under test is a pure helper, so this runs
on the 32-bit dev box.
"""
from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.services import admin_service as svc


# ---------------------------------------------------------------------------
# safe_rate / _avg (PRD §24)
# ---------------------------------------------------------------------------


def test_safe_rate_basic():
    assert svc.safe_rate(1, 4) == 0.25


def test_safe_rate_zero_denominator_is_zero():
    assert svc.safe_rate(5, 0) == 0.0


def test_safe_rate_never_negative():
    assert svc.safe_rate(-3, 10) == 0.0


def test_safe_rate_rounds():
    assert svc.safe_rate(1, 3) == 0.3333


def test_avg_empty_population_is_zero():
    assert svc._avg(100, 0) == 0.0


def test_avg_rounds_to_two():
    assert svc._avg(10, 3) == 3.33


# ---------------------------------------------------------------------------
# product_analytics (PRD §24.1)
# ---------------------------------------------------------------------------


def test_product_analytics_funnel_rates():
    out = svc.product_analytics({
        "registrations": 100,
        "verified_users": 80,
        "uploads_started": 50,
        "uploads_completed": 40,
        "jobs_total": 200,
        "jobs_succeeded": 180,
        "paid_users": 10,
    })
    assert out["registrations"] == 100
    assert out["email_verification_rate"] == 0.8
    assert out["upload_completion_rate"] == 0.8
    assert out["job_success_rate"] == 0.9
    assert out["plan_conversion_rate"] == 0.1


def test_product_analytics_missing_keys_default_zero():
    out = svc.product_analytics({})
    assert out["registrations"] == 0
    assert out["email_verification_rate"] == 0.0
    assert out["job_success_rate"] == 0.0


# ---------------------------------------------------------------------------
# processing_analytics (PRD §24.2)
# ---------------------------------------------------------------------------


def test_processing_analytics_failure_rate_by_bucket():
    out = svc.processing_analytics({
        "jobs_total": 100,
        "jobs_succeeded": 90,
        "processing_seconds_total": 600,
        "video_minutes_total": 10,
        "by_model": {"m1": {"total": 10, "failed": 2}, "m2": {"total": 0, "failed": 0}},
        "by_worker": {"w1": {"total": 4, "failed": 1}},
    })
    assert out["failure_rate_by_model"]["m1"] == 0.2
    assert out["failure_rate_by_model"]["m2"] == 0.0  # zero-denom safe
    assert out["failure_rate_by_worker"]["w1"] == 0.25
    assert out["avg_processing_seconds_per_minute"] == 60.0


def test_processing_analytics_empty_buckets():
    out = svc.processing_analytics({})
    assert out["failure_rate_by_model"] == {}
    assert out["avg_queue_seconds"] == 0.0


# ---------------------------------------------------------------------------
# cost_analytics (PRD §24.4) — paise ints
# ---------------------------------------------------------------------------


def test_cost_analytics_gpu_and_storage():
    out = svc.cost_analytics({
        "gpu_seconds_total": 3600,       # 1 GPU-hour
        "jobs_completed": 2,
        "active_users": 4,
        "projects_total": 8,
        "video_minutes_total": 10,
        "storage_bytes_total": 2 * (1024 ** 3),  # 2 GB
    })
    # 1 GPU-hour = 5000 paise total; per completed job of 2 = 2500
    assert out["total_gpu_cost_paise"] == 5000
    assert out["gpu_cost_per_completed_job_paise"] == 2500
    # 2 GB * 200 paise = 400 paise total
    assert out["total_storage_cost_paise"] == 400
    assert isinstance(out["storage_cost_per_user_paise"], int)


def test_cost_analytics_zero_usage_no_div_by_zero():
    out = svc.cost_analytics({})
    assert out["gpu_cost_per_completed_job_paise"] == 0
    assert out["total_gpu_cost_paise"] == 0


# ---------------------------------------------------------------------------
# exports (PRD §24.5)
# ---------------------------------------------------------------------------


def test_filter_export_rows_projects_allowed_columns():
    rows = [{"id": "1", "email": "a@b.c", "password_hash": "SECRET"}]
    out = svc.filter_export_rows(rows, ["id", "email"])
    assert out == [{"id": "1", "email": "a@b.c"}]
    assert "password_hash" not in out[0]


def test_filter_export_rows_missing_column_is_blank():
    out = svc.filter_export_rows([{"id": "1"}], ["id", "email"])
    assert out == [{"id": "1", "email": ""}]


def test_to_csv_header_and_escaping():
    rows = [{"a": "x,y", "b": 'he said "hi"'}, {"a": "line\nbreak", "b": "z"}]
    csv = svc.to_csv(rows, ["a", "b"])
    lines = csv.split("\r\n")
    assert lines[0] == "a,b"
    assert lines[1] == '"x,y","he said ""hi"""'
    assert lines[2].startswith('"line\nbreak"')


def test_to_csv_none_becomes_empty():
    assert svc.to_csv([{"a": None}], ["a"]) == "a\r\n"


def test_validate_export_format_accepts_known():
    assert svc.validate_export_format("CSV") == "csv"
    assert svc.validate_export_format("json") == "json"


def test_validate_export_format_rejects_unknown():
    with pytest.raises(AppError) as exc:
        svc.validate_export_format("xml")
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# system health (PRD §25.1 / §25.2)
# ---------------------------------------------------------------------------


def test_service_status_list_maps_all_names():
    rows = svc.service_status_list({"backend": True, "redis": False})
    names = {r["name"] for r in rows}
    assert names == set(svc.SERVICE_NAMES)
    by_name = {r["name"]: r["status"] for r in rows}
    assert by_name["backend"] == "operational"
    assert by_name["redis"] == "down"
    assert by_name["email"] == "unknown"  # missing → unknown


def test_health_status_for_thresholds():
    assert svc.health_status_for("queue_depth", 10) == "ok"
    assert svc.health_status_for("queue_depth", 60) == "warn"
    assert svc.health_status_for("queue_depth", 300) == "critical"


def test_health_status_for_unknown_metric_or_none():
    assert svc.health_status_for("nope", 5) == "unknown"
    assert svc.health_status_for("queue_depth", None) == "unknown"


def test_evaluate_health_metrics_covers_all_thresholds():
    rows = svc.evaluate_health_metrics({"queue_depth": 300})
    metrics = {r["metric"]: r for r in rows}
    assert metrics["queue_depth"]["status"] == "critical"
    # unmentioned metric present with unknown status
    assert metrics["api_response_ms"]["status"] == "unknown"


def test_overall_health_worst_wins():
    down_services = [{"status": "down"}]
    ok_metrics = [{"status": "ok"}]
    assert svc.overall_health(down_services, ok_metrics) == "critical"
    assert svc.overall_health([{"status": "operational"}], [{"status": "warn"}]) == "degraded"
    assert svc.overall_health([{"status": "operational"}], [{"status": "ok"}]) == "operational"


# ---------------------------------------------------------------------------
# incidents (PRD §25.4)
# ---------------------------------------------------------------------------


def test_incident_action_effects_resolve_requires_note():
    eff = svc.incident_action_effects("resolve")
    assert eff["status"] == "resolved"
    assert eff["requires_note"] is True


def test_incident_action_effects_silence():
    eff = svc.incident_action_effects("silence")
    assert eff["status"] is None
    assert eff["silence"] is True


def test_incident_action_effects_acknowledge():
    eff = svc.incident_action_effects("acknowledge")
    assert eff["status"] == "monitoring"


def test_validate_incident_action_rejects_unknown():
    with pytest.raises(AppError):
        svc.validate_incident_action("explode")


# ---------------------------------------------------------------------------
# administrator management (PRD §28.2 / §28.3)
# ---------------------------------------------------------------------------


def test_validate_admin_mgmt_action_rejects_self_suspend():
    with pytest.raises(AppError) as exc:
        svc.validate_admin_mgmt_action(
            "suspend", actor_id="a", target_id="a", target_admin_role="operations",
            reason="x",
        )
    assert exc.value.status_code == 422


def test_validate_admin_mgmt_action_role_change_needs_known_role():
    with pytest.raises(AppError):
        svc.validate_admin_mgmt_action(
            "change_role", actor_id="a", target_id="b", target_admin_role="operations",
            new_role="wizard",
        )


def test_validate_admin_mgmt_action_destructive_needs_reason():
    with pytest.raises(AppError):
        svc.validate_admin_mgmt_action(
            "remove", actor_id="a", target_id="b", target_admin_role="operations",
            reason="  ",
        )


def test_validate_admin_mgmt_action_happy_path():
    # valid role change to a known role, not self → no raise
    svc.validate_admin_mgmt_action(
        "change_role", actor_id="a", target_id="b", target_admin_role="support",
        new_role="billing",
    )


def test_validate_admin_mgmt_action_unknown_action():
    with pytest.raises(AppError):
        svc.validate_admin_mgmt_action(
            "teleport", actor_id="a", target_id="b", target_admin_role="support",
        )


# ---------------------------------------------------------------------------
# global search classifier (PRD §29)
# ---------------------------------------------------------------------------


def test_classify_search_razorpay_payment():
    assert svc.classify_search_query("pay_ABC123")[0] == "razorpay_payment"


def test_classify_search_order_and_sub():
    assert "payment" in svc.classify_search_query("order_XY9")
    assert svc.classify_search_query("sub_9z")[0] == "subscription"


def test_classify_search_email():
    assert svc.classify_search_query("user@example.com") == ["user"]


def test_classify_search_uuid_probes_many():
    hits = svc.classify_search_query("12345678-1234-1234-1234-123456789abc")
    assert "user" in hits and "project" in hits and "payment" in hits


def test_classify_search_promo_allcaps():
    hits = svc.classify_search_query("SAVE20")
    assert "promo" in hits


def test_classify_search_freetext_fallback():
    hits = svc.classify_search_query("alice")
    assert "user" in hits and "worker" in hits


def test_classify_search_empty():
    assert svc.classify_search_query("   ") == []


# ---------------------------------------------------------------------------
# secret handling (PRD §26.7) — never reveals private values
# ---------------------------------------------------------------------------


def test_describe_secret_private_never_reveals_value():
    d = svc.describe_secret("jwt_secret", "supersecretlongvalue")
    assert d["configured"] is True
    assert d["public"] is False
    assert d["value"] is None            # full value withheld
    assert d["last_four"] == "alue"      # only last 4 chars


def test_describe_secret_public_key_id_shown():
    d = svc.describe_secret("razorpay_key_id", "rzp_test_ABCD")
    assert d["public"] is True
    assert d["value"] == "rzp_test_ABCD"


def test_describe_secret_missing_is_not_configured():
    d = svc.describe_secret("email_password", "")
    assert d["configured"] is False
    assert d["value"] is None
    assert d["last_four"] == ""


def test_describe_secret_short_value_no_last_four():
    d = svc.describe_secret("jwt_secret", "ab")
    assert d["configured"] is True
    assert d["last_four"] == ""


def test_secret_keys_cover_expected():
    assert "database_url" in svc.SECRET_KEYS
    assert "razorpay_key_secret" in svc.SECRET_KEYS
