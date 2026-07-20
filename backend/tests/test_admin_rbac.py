"""Admin Panel Phase 1 — RBAC pure-logic tests (PRD §5, §33.1).

No DB / SQLAlchemy — runs on the 32-bit dev box. Covers the permission map
invariants, has_permission edge cases, and the legacy role mapping.
"""
from __future__ import annotations

import re

from app.services.admin_permissions import (
    ADMIN_ROLES,
    ALL_PERMISSIONS,
    PERMISSIONS,
    effective_admin_role,
    has_permission,
    permissions_for,
)


# ---------------------------------------------------------------------------
# Map completeness / shape invariants
# ---------------------------------------------------------------------------


def test_every_role_is_defined_in_the_map():
    assert set(ADMIN_ROLES) == set(PERMISSIONS.keys())


def test_every_permission_string_is_well_formed():
    pattern = re.compile(r"^[a-z]+\.[a-z_]+$")
    for perm in ALL_PERMISSIONS:
        assert pattern.match(perm), f"malformed permission: {perm}"


def test_role_grants_are_subsets_of_the_vocabulary():
    for role, grants in PERMISSIONS.items():
        unknown = grants - ALL_PERMISSIONS
        assert not unknown, f"{role} grants unknown permissions: {unknown}"


def test_super_admin_is_a_superset_of_every_role():
    su = PERMISSIONS["super_admin"]
    assert su == ALL_PERMISSIONS
    for role, grants in PERMISSIONS.items():
        assert grants <= su, f"{role} has permissions super_admin lacks"


def test_analyst_is_view_only():
    for perm in PERMISSIONS["analyst"]:
        assert perm.endswith(".view"), f"analyst holds a non-view permission: {perm}"


def test_operations_cannot_see_billing_or_manage_admins():
    ops = PERMISSIONS["operations"]
    assert "billing.view" not in ops
    assert "users.role" not in ops
    assert "users.delete" not in ops
    # ...but can run technical operations
    assert "jobs.manage" in ops
    assert "config.manage" in ops


def test_support_can_compensate_but_not_suspend():
    sup = PERMISSIONS["support"]
    assert "users.support" in sup
    assert "users.credits" in sup
    assert "notes.manage" in sup
    assert "users.manage" not in sup
    assert "config.manage" not in sup


def test_billing_scope():
    bil = PERMISSIONS["billing"]
    assert "billing.view" in bil
    assert "users.plan" in bil
    assert "users.credits" in bil
    assert "projects.manage" not in bil
    assert "jobs.manage" not in bil


def test_compliance_can_restrict_accounts_and_projects():
    com = PERMISSIONS["compliance"]
    assert "users.manage" in com
    assert "projects.manage" in com
    assert "abuse.manage" in com
    assert "audit.view" in com
    assert "config.manage" not in com


# ---------------------------------------------------------------------------
# has_permission / permissions_for edge cases
# ---------------------------------------------------------------------------


def test_has_permission_none_role_denies_everything():
    for perm in ALL_PERMISSIONS:
        assert not has_permission(None, perm)


def test_has_permission_unknown_role_denies():
    assert not has_permission("intern", "users.view")
    assert not has_permission("", "users.view")


def test_has_permission_grants_and_denies():
    assert has_permission("support", "users.support")
    assert not has_permission("support", "users.delete")
    assert has_permission("super_admin", "users.delete")


def test_permissions_for_sorted_and_empty_for_unknown():
    perms = permissions_for("analyst")
    assert perms == sorted(perms)
    assert permissions_for(None) == []
    assert permissions_for("intern") == []


# ---------------------------------------------------------------------------
# effective_admin_role — legacy mapping
# ---------------------------------------------------------------------------


def test_explicit_admin_role_wins():
    assert effective_admin_role("user", "support") == "support"
    assert effective_admin_role("admin", "analyst") == "analyst"


def test_legacy_admin_maps_to_super_admin():
    assert effective_admin_role("admin", None) == "super_admin"


def test_regular_user_is_not_staff():
    assert effective_admin_role("user", None) is None


def test_unknown_admin_role_falls_back():
    # Unknown role string on a legacy admin → still super_admin; on a normal
    # user → not staff.
    assert effective_admin_role("admin", "bogus") == "super_admin"
    assert effective_admin_role("user", "bogus") is None
