import type { LucideIcon } from "lucide-react";
import { BadgeDollarSign, LifeBuoy, Mail, UserCog } from "lucide-react";

export type AccountNavItem = { label: string; href: string; icon: LucideIcon };

/**
 * Account-specific actions. Deliberately excludes Projects / Upload / Dashboard
 * (already in the sidebar).
 */
export const accountActions: AccountNavItem[] = [
  // Self-service profile: edit name, avatar, password, delete account.
  { label: "Account settings", href: "/account", icon: UserCog },
  // Billing exists in the sidebar, but here it's framed as contextual account
  // management (plan, renewal, payment history), shown once and kept secondary.
  { label: "Subscription details", href: "/billing", icon: BadgeDollarSign },
];

/** Secondary support links — customer-facing pages that exist. */
export const accountSupportNav: AccountNavItem[] = [
  { label: "Help & Support", href: "/support", icon: LifeBuoy },
  { label: "Contact Support", href: "/contact", icon: Mail },
];
