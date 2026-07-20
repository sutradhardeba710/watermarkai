"""Admin Panel Phases 1+2 integration tests (VWA_INTEGRATION=1 gated).

Requires Postgres with migration 0004 applied. Covers:
  - RBAC: permission-denied for analyst on a mutation
  - Credit adjust: locked balance update + immutable ledger row
  - Audit: previous/new values + reason recorded
  - User detail bundle assembly
  - Project extend-retention action
"""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("VWA_INTEGRATION"),
    reason="Integration tests disabled (set VWA_INTEGRATION=1 to enable)",
)


@pytest.fixture()
def db():
    try:
        from app.core.db import SessionLocal
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"SQLAlchemy not available: {e}")
    db = SessionLocal()
    try:
        yield db
        db.rollback()
    finally:
        db.close()


@pytest.fixture()
def users(db):
    """A super admin + a regular target user, cleaned up after the test."""
    from app.models import AccountStatus, User, UserRole

    suffix = uuid.uuid4().hex[:8]
    admin = User(
        email=f"admin-{suffix}@test.local", full_name="Test Admin",
        password_hash="x", email_verified=True, role=UserRole.admin,
        admin_role="super_admin", account_status=AccountStatus.active,
    )
    target = User(
        email=f"user-{suffix}@test.local", full_name="Test User",
        password_hash="x", email_verified=True, role=UserRole.user,
        account_status=AccountStatus.active, credits_remaining=500,
    )
    db.add_all([admin, target])
    db.flush()
    yield admin, target
    db.rollback()


def test_analyst_denied_on_mutation_permission():
    """RBAC unit-of-truth: the same has_permission the dependency uses."""
    from app.services.admin_permissions import has_permission

    assert not has_permission("analyst", "users.credits")
    assert not has_permission("analyst", "projects.manage")
    assert has_permission("analyst", "users.view")


def test_adjust_credits_writes_ledger_and_audit(db, users):
    from app.models import AuditLog, CreditTransaction
    from app.services import admin_service

    admin, target = users
    result = admin_service.adjust_credits(
        db, admin=admin, target=target, amount=100, direction="credit",
        reason="integration-test compensation",
        audit_ctx={"request_id": "req-int-1"},
    )
    assert result["balance"] == 600
    assert target.credits_remaining == 600

    txn = db.get(CreditTransaction, result["transaction"].id)
    assert txn is not None
    assert txn.balance_before == 500
    assert txn.balance_after == 600
    assert txn.source == "admin"
    assert txn.admin_id == admin.id

    audit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "user.credits_adjust", AuditLog.target_id == target.id)
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert audit is not None
    assert audit.previous_data == {"credits_remaining": 500}
    assert audit.new_data == {"credits_remaining": 600}
    assert audit.reason == "integration-test compensation"
    assert audit.request_id == "req-int-1"


def test_adjust_credits_overdraft_conflict(db, users):
    from app.core.errors import AppError
    from app.services import admin_service

    admin, target = users
    with pytest.raises(AppError):
        admin_service.adjust_credits(
            db, admin=admin, target=target, amount=10_000, direction="debit",
            reason="too much",
        )


def test_user_detail_bundle(db, users):
    from app.services import admin_service

    admin, target = users
    detail = admin_service.get_user_detail(db, target)
    assert detail["email"] == target.email
    assert detail["credits_remaining"] == target.credits_remaining
    assert detail["plan_id"] == "free"
    assert detail["subscription"] is None


def test_project_extend_retention(db, users):
    from datetime import datetime, timedelta, timezone

    from app.models import ProjectStatus, VideoProject
    from app.services import admin_service

    admin, target = users
    project = VideoProject(
        user_id=target.id, title="Int test", original_filename="clip.mp4",
        status=ProjectStatus.completed,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(project)
    db.flush()
    before = project.expires_at
    admin_service.apply_project_action(
        db, admin=admin, project=project, action="extend_retention", hours=48,
    )
    assert project.expires_at > before
