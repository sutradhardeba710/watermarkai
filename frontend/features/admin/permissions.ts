// Frontend mirror of backend/app/services/admin_permissions.py.
// COSMETIC ONLY — used to hide nav items and action buttons. The server
// enforces every permission via require_permission on each route.
import type { AdminRole } from "@/types";
import type { AuthUser } from "@/features/auth/authStore";
import {
  BadgePercent,
  Bell,
  Boxes,
  BarChart3,
  CreditCard,
  Flag,
  FolderKanban,
  Gauge,
  HardDrive,
  Activity,
  KeyRound,
  Layers,
  ListChecks,
  Receipt,
  RefreshCw,
  Scale,
  ScrollText,
  Server,
  Settings,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Tags,
  Users,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const VIEW = [
  "overview.view", "users.view", "projects.view", "jobs.view", "workers.view",
  "config.view", "audit.view", "abuse.view", "billing.view", "notes.view",
  "models.view", "presets.view", "notifications.view",
  "analytics.view", "health.view",
];

const ALL = [
  ...VIEW,
  "users.manage", "users.support", "users.credits", "users.role", "users.plan",
  "users.delete", "projects.manage", "jobs.manage", "config.manage",
  "abuse.manage", "notes.manage", "billing.manage", "plans.manage", "promos.manage",
  "models.manage", "presets.manage", "notifications.manage", "flags.manage", "maintenance.manage",
  "analytics.export", "health.manage", "admins.manage",
  // super-admin-only restricted permissions (§28.3, §26.7)
  "admins.view", "secrets.view",
];

export const PERMISSIONS: Record<AdminRole, string[]> = {
  super_admin: ALL,
  operations: [
    ...VIEW.filter((p) => p !== "billing.view"),
    "projects.manage", "jobs.manage", "config.manage",
    "models.manage", "presets.manage", "notifications.manage", "flags.manage", "maintenance.manage",
    "health.manage",
  ],
  support: [
    "overview.view", "users.view", "users.support", "users.credits",
    "projects.view", "jobs.view", "notes.view", "notes.manage", "abuse.view",
  ],
  billing: [
    "overview.view", "users.view", "users.credits", "users.plan",
    "billing.view", "billing.manage", "plans.manage", "promos.manage", "notes.view",
    "analytics.view", "analytics.export",
  ],
  compliance: [
    "overview.view", "users.view", "users.manage", "projects.view", "projects.manage",
    "abuse.view", "abuse.manage", "audit.view", "notes.view", "notes.manage",
  ],
  analyst: VIEW,
};

/** Resolve the effective admin role: explicit admin_role wins; legacy
 * role==="admin" with no admin_role maps to super_admin. */
export function effectiveAdminRole(user: AuthUser | null): AdminRole | null {
  if (!user) return null;
  if (user.admin_role && user.admin_role in PERMISSIONS) return user.admin_role as AdminRole;
  if (user.role === "admin") return "super_admin";
  return null;
}

export function hasPermission(user: AuthUser | null, permission: string): boolean {
  const role = effectiveAdminRole(user);
  if (!role) return false;
  return PERMISSIONS[role].includes(permission);
}

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  permission: string;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/admin", label: "Overview", icon: Gauge, permission: "overview.view" },
  { href: "/admin/users", label: "Users", icon: Users, permission: "users.view" },
  { href: "/admin/projects", label: "Projects", icon: FolderKanban, permission: "projects.view" },
  { href: "/admin/jobs", label: "Jobs", icon: ListChecks, permission: "jobs.view" },
  { href: "/admin/queue", label: "Queues", icon: Layers, permission: "jobs.view" },
  { href: "/admin/workers", label: "Workers", icon: Server, permission: "workers.view" },
  { href: "/admin/billing", label: "Billing", icon: CreditCard, permission: "billing.view" },
  { href: "/admin/payments", label: "Payments", icon: Receipt, permission: "billing.view" },
  { href: "/admin/subscriptions", label: "Subscriptions", icon: RefreshCw, permission: "billing.view" },
  { href: "/admin/plans", label: "Plans", icon: Tags, permission: "billing.view" },
  { href: "/admin/promos", label: "Promo codes", icon: BadgePercent, permission: "billing.view" },
  { href: "/admin/credits", label: "Credits", icon: Layers, permission: "billing.view" },
  { href: "/admin/storage", label: "Storage", icon: HardDrive, permission: "projects.view" },
  { href: "/admin/compliance", label: "Compliance", icon: Scale, permission: "abuse.view" },
  { href: "/admin/models", label: "AI models", icon: Boxes, permission: "models.view" },
  { href: "/admin/presets", label: "Presets", icon: SlidersHorizontal, permission: "presets.view" },
  { href: "/admin/notifications", label: "Notifications", icon: Bell, permission: "notifications.view" },
  { href: "/admin/feature-flags", label: "Feature flags", icon: Flag, permission: "config.view" },
  { href: "/admin/maintenance", label: "Maintenance", icon: Wrench, permission: "config.view" },
  { href: "/admin/audit", label: "Audit log", icon: ScrollText, permission: "audit.view" },
  { href: "/admin/abuse", label: "Abuse", icon: ShieldAlert, permission: "abuse.view" },
  { href: "/admin/analytics", label: "Analytics", icon: BarChart3, permission: "analytics.view" },
  { href: "/admin/system-health", label: "System health", icon: Activity, permission: "health.view" },
  { href: "/admin/administrators", label: "Administrators", icon: ShieldCheck, permission: "admins.view" },
  { href: "/admin/secrets", label: "Secrets", icon: KeyRound, permission: "secrets.view" },
  { href: "/admin/settings", label: "Settings", icon: Settings, permission: "config.view" },
];

export const ROLE_LABELS: Record<AdminRole, string> = {
  super_admin: "Super admin",
  operations: "Operations",
  support: "Support",
  billing: "Billing",
  compliance: "Compliance",
  analyst: "Analyst",
};

export const ADMIN_ROLES = Object.keys(ROLE_LABELS) as AdminRole[];
