import type { LucideIcon } from "lucide-react";
import { BadgeDollarSign, LifeBuoy, Mail } from "lucide-react";

export type AccountNavItem = { label: string; href: string; icon: LucideIcon };

/**
 * Account-specific actions. Deliberately excludes Projects / Upload / Dashboard
 * (already in the sidebar) and any /settings/* routes that don't exist yet.
 *
 * Add Account Settings / Security / Notifications / Usage here only once those
 * routes ship — the menu should never link to a missing page.
 */
export const accountActions: AccountNavItem[] = [
  // Billing exists in the sidebar, but here it's framed as contextual account
  // management (plan, renewal, payment history), shown once and kept secondary.
  { label: "Subscription details", href: "/billing", icon: BadgeDollarSign },
];

/** Secondary support links — customer-facing pages that exist. */
export const accountSupportNav: AccountNavItem[] = [
  { label: "Help & Support", href: "/support", icon: LifeBuoy },
  { label: "Contact Support", href: "/contact", icon: Mail },
];
