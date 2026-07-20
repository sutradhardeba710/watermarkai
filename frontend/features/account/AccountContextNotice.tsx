"use client";

import Link from "next/link";
import { AlertTriangle, CalendarClock, Info } from "lucide-react";

import type { AuthUser } from "@/features/auth/authStore";
import type { SubscriptionStatus } from "@/services/payments";
import { formatResetDate } from "./CompactAccountSummary";

const LOW_CREDIT_THRESHOLD = 15;

type Notice = {
  tone: "warn" | "info";
  icon: typeof AlertTriangle;
  message: string;
  action?: { label: string; href: string };
};

/**
 * Derive the single highest-priority account notice from real data.
 * Priority: cancellation pending → low credits → renewal soon → none.
 * Email verification is intentionally omitted: there is no resend endpoint,
 * so a "Send verification email" action would be a dead button.
 */
function deriveNotice(
  user: AuthUser,
  status: SubscriptionStatus | undefined,
): Notice | null {
  if (!status) return null;

  if (status.subscription_status === "cancelled" && status.current_period_end) {
    const ends = formatResetDate(status.current_period_end);
    if (ends) {
      return {
        tone: "warn",
        icon: AlertTriangle,
        message: `Your ${status.plan_name} plan ends on ${ends}.`,
        action: { label: "Manage subscription", href: "/billing" },
      };
    }
  }

  if (!status.is_free && status.credits_remaining <= LOW_CREDIT_THRESHOLD) {
    return {
      tone: "warn",
      icon: AlertTriangle,
      message: `Only ${status.credits_remaining.toLocaleString("en-IN")} credits remaining.`,
      action: { label: "View plans", href: "/pricing" },
    };
  }

  if (status.is_free) {
    return {
      tone: "info",
      icon: Info,
      message: "You're on the Free plan. Upgrade for more daily credits.",
      action: { label: "View plans", href: "/pricing" },
    };
  }

  if (status.current_period_end && status.subscription_status === "active") {
    const renews = formatResetDate(status.current_period_end);
    if (renews) {
      return {
        tone: "info",
        icon: CalendarClock,
        message: `Your ${status.plan_name} plan renews on ${renews}.`,
      };
    }
  }

  return null;
}

export function AccountContextNotice({
  user,
  status,
}: {
  user: AuthUser;
  status: SubscriptionStatus | undefined;
}) {
  const notice = deriveNotice(user, status);
  if (!notice) return null;

  const Icon = notice.icon;
  const toneRing =
    notice.tone === "warn"
      ? "border-amber-400/25 bg-amber-400/[.07] text-amber-100/90"
      : "border-white/10 bg-white/[.04] text-white/70";
  const iconColor = notice.tone === "warn" ? "text-amber-300" : "text-cyan-300";

  return (
    <div className={`mx-1 rounded-lg border px-2.5 py-2 ${toneRing}`}>
      <div className="flex gap-2">
        <Icon aria-hidden className={`mt-0.5 h-4 w-4 shrink-0 ${iconColor}`} />
        <div className="min-w-0">
          <p className="text-xs leading-5">{notice.message}</p>
          {notice.action && (
            <Link
              href={notice.action.href}
              className="mt-1 inline-block text-xs font-medium text-[#b7c7ff] transition hover:text-white"
            >
              {notice.action.label} →
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
