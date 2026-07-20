"""Admin RBAC permission map (PRD §5, §33.1). Pure module — ZERO ORM imports
so it stays unit-testable on the 32-bit dev box.

Permissions are dot-namespaced ``resource.verb`` strings. Roles map to frozen
permission sets; ``super_admin`` is the union of everything. The check used by
routes is :func:`has_permission`, wired through
``app.auth.dependencies.require_permission``.

Legacy mapping: a user with ``role == 'admin'`` and no ``admin_role`` is
treated as ``super_admin`` (:func:`effective_admin_role`) so existing admins
keep working without a data fix beyond the 0004 migration backfill.
"""
from __future__ import annotations

from typing import Optional

# --- Permission vocabulary ---

_VIEW_PERMISSIONS = frozenset({
    "overview.view",
    "users.view",
    "projects.view",
    "jobs.view",
    "workers.view",
    "config.view",
    "audit.view",
    "abuse.view",
    "billing.view",
    "notes.view",
    "models.view",         # AI model registry (PRD §19)
    "presets.view",        # processing presets (PRD §20)
    "notifications.view",  # templates + broadcasts (PRD §23)
    "analytics.view",      # analytics & reports (PRD §24)
    "health.view",         # system health board (PRD §25)
})

_MANAGE_PERMISSIONS = frozenset({
    "users.manage",     # suspend / ban / restore / delete-adjacent status changes
    "users.support",    # verify email, resend verification, password reset, revoke sessions
    "users.credits",    # add/remove credits
    "users.role",       # change admin role
    "users.plan",       # change plan
    "users.delete",     # soft-delete account
    "projects.manage",  # retention, lock, expire, delete files
    "jobs.manage",      # retry / cancel
    "config.manage",
    "abuse.manage",
    "notes.manage",
    "billing.manage",   # verify/reprocess/refund payments, subscription actions
    "plans.manage",     # plan catalog CRUD
    "promos.manage",    # promo code CRUD
    "models.manage",        # register/activate/rollback AI models (PRD §19)
    "presets.manage",       # preset CRUD (PRD §20)
    "notifications.manage", # edit templates, send broadcasts (PRD §23)
    "flags.manage",         # toggle feature flags (PRD §26.5)
    "maintenance.manage",   # maintenance mode window (PRD §26.6)
    "analytics.export",     # download analytics/report exports (PRD §24.5)
    "health.manage",        # ack/silence/resolve incidents (PRD §25.4)
    "admins.manage",        # invite/role/suspend administrators (PRD §28)
})

# Super-admin-only permissions (PRD §28.3): administrator management and secret
# descriptors. Kept OUT of the view/manage vocab so no lesser role (analyst,
# operations, …) can inherit them — only the explicit super_admin union grants
# these. Still part of ALL_PERMISSIONS so super_admin receives them.
_RESTRICTED_PERMISSIONS = frozenset({
    "admins.view",     # administrator list (PRD §28.1)
    "secrets.view",    # secret descriptors — never full values (PRD §26.7)
})

ALL_PERMISSIONS = _VIEW_PERMISSIONS | _MANAGE_PERMISSIONS | _RESTRICTED_PERMISSIONS

ADMIN_ROLES = (
    "super_admin",
    "operations",
    "support",
    "billing",
    "compliance",
    "analyst",
)

# --- Role grants (PRD §5.1–5.6) ---

PERMISSIONS: dict[str, frozenset[str]] = {
    # Full access to every module (PRD §5.1).
    "super_admin": frozenset(ALL_PERMISSIONS),
    # Technical operations: jobs/queues/workers/config; no billing or admin
    # management (PRD §5.2).
    "operations": (_VIEW_PERMISSIONS - frozenset({"billing.view"})) | frozenset({
        "projects.manage",
        "jobs.manage",
        "config.manage",
        "models.manage",
        "presets.manage",
        "notifications.manage",
        "flags.manage",
        "maintenance.manage",
        "health.manage",
    }),
    # Customer support: users + notes + limited compensation (PRD §5.3).
    "support": frozenset({
        "overview.view",
        "users.view",
        "users.support",
        "users.credits",
        "projects.view",
        "jobs.view",
        "notes.view",
        "notes.manage",
        "abuse.view",
    }),
    # Financial operations (PRD §5.4).
    "billing": frozenset({
        "overview.view",
        "users.view",
        "users.credits",
        "users.plan",
        "billing.view",
        "billing.manage",
        "plans.manage",
        "promos.manage",
        "notes.view",
        "analytics.view",
        "analytics.export",
    }),
    # Abuse/compliance review; may restrict or suspend accounts (PRD §5.5).
    "compliance": frozenset({
        "overview.view",
        "users.view",
        "users.manage",
        "projects.view",
        "projects.manage",
        "abuse.view",
        "abuse.manage",
        "audit.view",
        "notes.view",
        "notes.manage",
    }),
    # Read-only analyst (PRD §5.6).
    "analyst": frozenset(_VIEW_PERMISSIONS),
}


def effective_admin_role(role: str, admin_role: Optional[str]) -> Optional[str]:
    """Resolve the admin-panel role for a user.

    ``admin_role`` wins when set and known. A legacy ``role == 'admin'`` user
    with no admin_role is a super_admin. Everyone else is not staff → None.
    """
    if admin_role in PERMISSIONS:
        return admin_role
    if role == "admin":
        return "super_admin"
    return None


def has_permission(admin_role: Optional[str], permission: str) -> bool:
    """True when ``admin_role`` (already resolved) grants ``permission``."""
    if admin_role is None:
        return False
    return permission in PERMISSIONS.get(admin_role, frozenset())


def permissions_for(admin_role: Optional[str]) -> list[str]:
    """Sorted permission list for an admin role (empty for unknown/None)."""
    if admin_role is None:
        return []
    return sorted(PERMISSIONS.get(admin_role, frozenset()))


__all__ = [
    "ADMIN_ROLES",
    "ALL_PERMISSIONS",
    "PERMISSIONS",
    "effective_admin_role",
    "has_permission",
    "permissions_for",
]
