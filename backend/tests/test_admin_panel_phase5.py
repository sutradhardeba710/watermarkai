"""Admin Panel Phase 5 pure-logic tests — storage & compliance policy
(PRD §18, §21).

No DB / SQLAlchemy — runs on the 32-bit dev box.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import AppError
from app.services import admin_service as svc


NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# storage_overview (PRD §18.1)
# ---------------------------------------------------------------------------


def test_storage_overview_sums_known_buckets():
    rows = [
        {"bucket": "input", "bytes": 1000},
        {"bucket": "output", "bytes": 2000},
        {"bucket": "preview", "bytes": 500},
    ]
    ov = svc.storage_overview(rows)
    assert ov["total_bytes"] == 3500
    assert ov["buckets"]["input"] == 1000
    assert ov["buckets"]["output"] == 2000
    assert ov["buckets"]["preview"] == 500
    # untouched buckets default to zero
    assert ov["buckets"]["mask"] == 0
    assert ov["buckets"]["frames"] == 0


def test_storage_overview_unknown_bucket_counts_as_orphaned():
    ov = svc.storage_overview([{"bucket": "weird", "bytes": 999}])
    assert ov["buckets"]["orphaned"] == 999
    assert ov["total_bytes"] == 999


def test_storage_overview_empty_is_all_zero():
    ov = svc.storage_overview([])
    assert ov["total_bytes"] == 0
    assert ov["estimated_cost_inr"] == 0
    assert set(ov["buckets"]) >= set(svc.STORAGE_BUCKETS)


def test_storage_overview_cost_scales_with_gb():
    one_gb = 1024 ** 3
    ov = svc.storage_overview([{"bucket": "output", "bytes": one_gb}])
    # ₹2.00 / GB-month = 200 paise
    assert ov["estimated_cost_inr"] == 200


def test_storage_overview_handles_none_bytes():
    ov = svc.storage_overview([{"bucket": "output", "bytes": None}])
    assert ov["buckets"]["output"] == 0


# ---------------------------------------------------------------------------
# storage_deletion_allowed (PRD §18.5)
# ---------------------------------------------------------------------------


def test_deletion_allowed_when_clean():
    allowed, reason = svc.storage_deletion_allowed(
        has_active_job=False, legal_hold=False, locked=False, has_open_dispute=False
    )
    assert allowed is True
    assert reason is None


def test_deletion_blocked_by_active_job_first():
    allowed, reason = svc.storage_deletion_allowed(
        has_active_job=True, legal_hold=True, locked=True, has_open_dispute=True
    )
    assert allowed is False
    assert reason == "active_job"


def test_deletion_blocked_by_legal_hold():
    allowed, reason = svc.storage_deletion_allowed(
        has_active_job=False, legal_hold=True, locked=False, has_open_dispute=False
    )
    assert allowed is False
    assert reason == "legal_hold"


def test_deletion_blocked_by_lock():
    allowed, reason = svc.storage_deletion_allowed(
        has_active_job=False, legal_hold=False, locked=True, has_open_dispute=False
    )
    assert allowed is False
    assert reason == "compliance_lock"


def test_deletion_blocked_by_open_dispute():
    allowed, reason = svc.storage_deletion_allowed(
        has_active_job=False, legal_hold=False, locked=False, has_open_dispute=True
    )
    assert allowed is False
    assert reason == "open_dispute"


# ---------------------------------------------------------------------------
# retention_bucket (PRD §18.3)
# ---------------------------------------------------------------------------


def test_retention_bucket_legal_hold_wins():
    b = svc.retention_bucket(NOW - timedelta(days=100), legal_hold=True, now=NOW)
    assert b == "locked"


def test_retention_bucket_failed_cleanup():
    b = svc.retention_bucket(NOW + timedelta(days=30), cleanup_failed=True, now=NOW)
    assert b == "failed_cleanup"


def test_retention_bucket_past_retention():
    assert svc.retention_bucket(NOW - timedelta(hours=1), now=NOW) == "past_retention"


def test_retention_bucket_expiring_today():
    assert svc.retention_bucket(NOW + timedelta(hours=5), now=NOW) == "expiring_today"


def test_retention_bucket_expiring_soon():
    assert svc.retention_bucket(NOW + timedelta(days=3), now=NOW) == "expiring_soon"


def test_retention_bucket_extended_when_far_out():
    b = svc.retention_bucket(NOW + timedelta(days=30), retention_extended=True, now=NOW)
    assert b == "extended"


def test_retention_bucket_active_default():
    assert svc.retention_bucket(NOW + timedelta(days=30), now=NOW) == "active"


def test_retention_bucket_naive_datetime_ok():
    naive = (NOW + timedelta(hours=5)).replace(tzinfo=None)
    assert svc.retention_bucket(naive, now=NOW) == "expiring_today"


def test_retention_bucket_none_expiry_is_active():
    assert svc.retention_bucket(None, now=NOW) == "active"


# ---------------------------------------------------------------------------
# validate_abuse_severity (PRD §21.2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sev", ["low", "medium", "high", "critical", "HIGH", " Low "])
def test_validate_abuse_severity_accepts(sev):
    assert svc.validate_abuse_severity(sev) in svc.ABUSE_SEVERITIES


def test_validate_abuse_severity_rejects_unknown():
    with pytest.raises(AppError):
        svc.validate_abuse_severity("catastrophic")


# ---------------------------------------------------------------------------
# compliance_action_effects (PRD §21.5)
# ---------------------------------------------------------------------------


def test_compliance_effects_place_legal_hold():
    e = svc.compliance_action_effects("place_legal_hold")
    assert e["report_status"] == "legal_hold"
    assert e["project"]["legal_hold"] is True
    assert e["project"]["locked"] is True
    assert e["requires_reason"] is True


def test_compliance_effects_remove_legal_hold():
    e = svc.compliance_action_effects("remove_legal_hold")
    assert e["project"]["legal_hold"] is False
    assert e["requires_reason"] is True


def test_compliance_effects_restrict_processing():
    e = svc.compliance_action_effects("restrict_processing")
    assert e["project"]["processing_restricted"] is True
    assert e["report_status"] == "action_required"


def test_compliance_effects_disable_downloads():
    e = svc.compliance_action_effects("disable_downloads")
    assert e["project"]["downloads_disabled"] is True


def test_compliance_effects_ban_account_sets_status_and_reason():
    e = svc.compliance_action_effects("ban_account")
    assert e["account_status"] == "banned"
    assert e["requires_reason"] is True


def test_compliance_effects_suspend_account():
    e = svc.compliance_action_effects("suspend_account")
    assert e["account_status"] == "suspended"
    assert e["requires_reason"] is True


def test_compliance_effects_mark_safe_resolves():
    e = svc.compliance_action_effects("mark_safe")
    assert e["report_status"] == "resolved"
    assert e["project"] == {}
    assert e["account_status"] is None


def test_compliance_effects_add_note_requires_reason_only():
    e = svc.compliance_action_effects("add_note")
    assert e["requires_reason"] is True
    assert e["report_status"] is None
    assert e["project"] == {}


def test_compliance_effects_escalate():
    assert svc.compliance_action_effects("escalate")["report_status"] == "escalated"


def test_compliance_effects_rejects_unknown():
    with pytest.raises(AppError):
        svc.compliance_action_effects("nuke_everything")


# ---------------------------------------------------------------------------
# compliance_overview (PRD §21.1)
# ---------------------------------------------------------------------------


def test_compliance_overview_fills_defaults():
    ov = svc.compliance_overview({"open_reviews": 3})
    assert ov["open_reviews"] == 3
    assert ov["projects_on_legal_hold"] == 0
    assert ov["ownership_confirmations"] == 0
    # all §21.1 keys present
    for key in (
        "ownership_confirmations", "projects_reported", "open_reviews",
        "suspended_accounts", "repeat_offenders", "high_risk_uploads",
        "missing_confirmations", "projects_on_legal_hold",
    ):
        assert key in ov


def test_compliance_overview_coerces_none():
    ov = svc.compliance_overview({"projects_reported": None})
    assert ov["projects_reported"] == 0
