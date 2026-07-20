"use client";

import type { SubscriptionStatus } from "@/services/payments";

function ValueSkeleton() {
  return <span className="mt-1 block h-4 w-20 animate-pulse rounded bg-white/10" />;
}

/** Format an ISO date as "1 August" (day + month), or null if absent/invalid. */
export function formatResetDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "long" });
}

/**
 * Compact two-column account summary: credits remaining + renewal/reset date.
 * Deliberately NOT the sidebar's full progress-bar card — just the numbers.
 */
export function CompactAccountSummary({
  status,
  isLoading,
  isError,
}: {
  status: SubscriptionStatus | undefined;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isError) {
    return <p className="px-1 text-xs text-white/40">Account details unavailable right now.</p>;
  }

  const renewal = formatResetDate(status?.current_period_end);
  const cancelled = status?.subscription_status === "cancelled";

  return (
    <div className="grid grid-cols-2 gap-3 px-1">
      <div>
        <p className="text-[11px] uppercase tracking-wide text-white/35">Credits</p>
        {isLoading || !status ? (
          <ValueSkeleton />
        ) : (
          <p className="mt-1 text-sm font-medium text-white">
            {status.credits_remaining.toLocaleString("en-IN")}{" "}
            <span className="font-normal text-white/45">left</span>
          </p>
        )}
      </div>
      <div>
        <p className="text-[11px] uppercase tracking-wide text-white/35">
          {cancelled ? "Ends" : "Renews"}
        </p>
        {isLoading || !status ? (
          <ValueSkeleton />
        ) : (
          <p className="mt-1 text-sm font-medium text-white">
            {status.is_free ? "—" : renewal ?? "—"}
          </p>
        )}
      </div>
    </div>
  );
}
