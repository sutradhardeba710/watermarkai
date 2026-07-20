"""Admin Panel Phase 2 pure-logic tests — pagination, credit-transaction
builder, user-action guards, retention math, overview extras, and the new
Pydantic request validators (PRD §8, §9, §17, §27, §30.5).

No DB / SQLAlchemy — runs on the 32-bit dev box, mirroring test_admin_phase8.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.admin import (
    AdminOverview,
    AdminUserActionRequest,
    CreditAdjustRequest,
    PlanChangeRequest,
    ProjectActionRequest,
    RoleChangeRequest,
    SupportNoteCreate,
)
from app.services import admin_service


# ---------------------------------------------------------------------------
# paginate / page_envelope
# ---------------------------------------------------------------------------


def test_paginate_defaults_and_offsets():
    page, size, limit, offset = admin_service.paginate(1, 25)
    assert (page, size, limit, offset) == (1, 25, 25, 0)
    page, size, limit, offset = admin_service.paginate(3, 10)
    assert (page, size, limit, offset) == (3, 10, 10, 20)


def test_paginate_clamps_page_and_size():
    page, size, limit, offset = admin_service.paginate(0, 0)
    assert page == 1 and size == 1 and offset == 0
    page, size, limit, offset = admin_service.paginate(-5, 10_000)
    assert page == 1 and size == admin_service.MAX_PAGE_SIZE
    _, size, _, _ = admin_service.paginate(1, 500, max_page_size=50)
    assert size == 50


def test_paginate_tolerates_junk():
    page, size, limit, offset = admin_service.paginate(None, "abc")
    assert page == 1 and size == admin_service.DEFAULT_PAGE_SIZE


def test_page_envelope_shape():
    env = admin_service.page_envelope(["a"], 42, 2, 25)
    assert env == {"items": ["a"], "total": 42, "page": 2, "page_size": 25}


# ---------------------------------------------------------------------------
# build_credit_txn (PRD §17.2)
# ---------------------------------------------------------------------------


def test_credit_txn_credit_math():
    txn = admin_service.build_credit_txn(
        user_id="u1", balance_before=100, amount=50, direction="credit",
        source="admin", reason="compensation", admin_id="a1",
    )
    assert txn["balance_after"] == 150
    assert txn["direction"] == "credit"
    assert txn["admin_id"] == "a1"


def test_credit_txn_debit_math():
    txn = admin_service.build_credit_txn(
        user_id="u1", balance_before=100, amount=40, direction="debit", source="job",
    )
    assert txn["balance_after"] == 60


def test_credit_txn_rejects_overdraft():
    with pytest.raises(ValueError, match="overdraw"):
        admin_service.build_credit_txn(
            user_id="u1", balance_before=30, amount=40, direction="debit", source="admin",
        )


def test_credit_txn_rejects_bad_amount_direction_source():
    with pytest.raises(ValueError, match="positive"):
        admin_service.build_credit_txn(
            user_id="u1", balance_before=10, amount=0, direction="credit", source="admin",
        )
    with pytest.raises(ValueError, match="direction"):
        admin_service.build_credit_txn(
            user_id="u1", balance_before=10, amount=5, direction="up", source="admin",
        )
    with pytest.raises(ValueError, match="source"):
        admin_service.build_credit_txn(
            user_id="u1", balance_before=10, amount=5, direction="credit", source="mystery",
        )


# ---------------------------------------------------------------------------
# validate_user_admin_action guard rails
# ---------------------------------------------------------------------------


def test_cannot_suspend_yourself():
    with pytest.raises(ValueError, match="own account"):
        admin_service.validate_user_admin_action(
            action="suspend", actor_id="a1", target_id="a1",
            target_is_staff=True, actor_is_super=True,
        )


def test_self_safe_actions_allowed():
    # Non-status-changing action on yourself is fine.
    admin_service.validate_user_admin_action(
        action="verify_email", actor_id="a1", target_id="a1",
        target_is_staff=True, actor_is_super=True,
    )


def test_only_super_can_act_on_staff():
    with pytest.raises(ValueError, match="super administrator"):
        admin_service.validate_user_admin_action(
            action="suspend", actor_id="a1", target_id="u2",
            target_is_staff=True, actor_is_super=False,
        )
    # Super admin can.
    admin_service.validate_user_admin_action(
        action="suspend", actor_id="a1", target_id="u2",
        target_is_staff=True, actor_is_super=True,
    )


def test_non_staff_target_allows_non_super_actor():
    admin_service.validate_user_admin_action(
        action="ban", actor_id="a1", target_id="u2",
        target_is_staff=False, actor_is_super=False,
    )


# ---------------------------------------------------------------------------
# extend_retention_expiry
# ---------------------------------------------------------------------------


def test_extend_from_future_expiry_extends_the_expiry():
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    current = now + timedelta(hours=10)
    out = admin_service.extend_retention_expiry(current, 24, now=now)
    assert out == current + timedelta(hours=24)


def test_extend_from_past_expiry_extends_from_now():
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    stale = now - timedelta(days=3)
    out = admin_service.extend_retention_expiry(stale, 24, now=now)
    assert out == now + timedelta(hours=24)


def test_extend_with_no_expiry_uses_now():
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    out = admin_service.extend_retention_expiry(None, 48, now=now)
    assert out == now + timedelta(hours=48)


def test_extend_handles_naive_datetimes():
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    naive = datetime(2026, 7, 20, 12, 0)  # future, no tzinfo
    out = admin_service.extend_retention_expiry(naive, 1, now=now)
    assert out.tzinfo is not None


# ---------------------------------------------------------------------------
# overview_extras
# ---------------------------------------------------------------------------


def test_success_rate_computed():
    extras = admin_service.overview_extras({"jobs_completed_today": 8, "jobs_failed_today": 2})
    assert extras["success_rate"] == 0.8


def test_success_rate_none_when_no_jobs():
    extras = admin_service.overview_extras({"jobs_completed_today": 0, "jobs_failed_today": 0})
    assert extras["success_rate"] is None
    extras = admin_service.overview_extras({})
    assert extras["success_rate"] is None


def test_admin_overview_schema_backward_compatible():
    # Old-shape payload (Phase 8) still validates — new fields default None.
    o = AdminOverview(
        total_users=1, active_users=1, suspended_users=0, jobs_today=0,
        queue_length=0, completed_jobs=0, failed_jobs=0, gpu_workers=0,
        storage_bytes=0,
    )
    assert o.users_today is None
    assert o.success_rate is None


# ---------------------------------------------------------------------------
# Pydantic request validators
# ---------------------------------------------------------------------------


def test_user_action_request_accepts_known_actions():
    for action in ("verify_email", "resend_verification", "revoke_sessions", "restore"):
        assert AdminUserActionRequest(action=action).action == action


def test_user_action_request_rejects_unknown():
    with pytest.raises(ValidationError):
        AdminUserActionRequest(action="nuke")


def test_destructive_user_actions_require_reason():
    with pytest.raises(ValidationError):
        AdminUserActionRequest(action="suspend")
    with pytest.raises(ValidationError):
        AdminUserActionRequest(action="ban", reason="  ")
    ok = AdminUserActionRequest(action="suspend", reason="ToS violation")
    assert ok.reason == "ToS violation"
    with pytest.raises(ValidationError):
        AdminUserActionRequest(action="delete_account")


def test_role_change_request_validates_roles():
    assert RoleChangeRequest(admin_role="support").admin_role == "support"
    assert RoleChangeRequest(admin_role=None).admin_role is None
    with pytest.raises(ValidationError):
        RoleChangeRequest(admin_role="root")


def test_credit_adjust_request_rules():
    ok = CreditAdjustRequest(amount=100, direction="credit", reason="compensation")
    assert ok.amount == 100
    with pytest.raises(ValidationError):
        CreditAdjustRequest(amount=0, direction="credit", reason="compensation")
    with pytest.raises(ValidationError):
        CreditAdjustRequest(amount=10, direction="sideways", reason="compensation")
    with pytest.raises(ValidationError):
        CreditAdjustRequest(amount=10, direction="debit", reason="ab")  # reason too short


def test_project_action_request_rules():
    ok = ProjectActionRequest(action="extend_retention", hours=24)
    assert ok.hours == 24
    with pytest.raises(ValidationError):
        ProjectActionRequest(action="extend_retention")  # hours required
    with pytest.raises(ValidationError):
        ProjectActionRequest(action="expire_now")  # reason required
    with pytest.raises(ValidationError):
        ProjectActionRequest(action="delete_files")  # reason required
    assert ProjectActionRequest(action="lock", reason="review").action == "lock"
    assert ProjectActionRequest(action="unlock").action == "unlock"
    with pytest.raises(ValidationError):
        ProjectActionRequest(action="explode")


def test_plan_change_and_note_validators():
    assert PlanChangeRequest(plan_id="pro").plan_id == "pro"
    with pytest.raises(ValidationError):
        PlanChangeRequest(plan_id="")
    assert SupportNoteCreate(body="hello").pinned is False
    with pytest.raises(ValidationError):
        SupportNoteCreate(body="")
