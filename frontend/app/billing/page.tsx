"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  ArrowUpRight,
  Calendar,
  Check,
  ChevronRight,
  Shield,
  Zap,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { useAuthStore } from "@/features/auth/authStore";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { paymentsApi, type SubscriptionStatus } from "@/services/payments";

const PLAN_COLORS: Record<string, string> = {
  free: "from-white/10 to-white/5",
  starter: "from-[#4f7cff]/30 to-[#6d5ef7]/20",
  pro: "from-[#6d5ef7]/30 to-[#22d3ee]/20",
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-400/15 text-emerald-300 border-emerald-400/20",
  past_due: "bg-amber-400/15 text-amber-200 border-amber-400/20",
  cancelled: "bg-rose-400/15 text-rose-300 border-rose-400/20",
  trialing: "bg-sky-400/15 text-sky-200 border-sky-400/20",
};

function CreditBar({ used, total }: { used: number; total: number }) {
  const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0;
  const color = pct > 80 ? "from-rose-500 to-rose-400" : pct > 50 ? "from-amber-400 to-amber-300" : "from-[#4f7cff] to-[#22d3ee]";
  return (
    <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        className={`h-full rounded-full bg-gradient-to-r ${color}`}
      />
    </div>
  );
}

export default function BillingPage() {
  useHydrateAuth();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const hydrated = useAuthStore((s) => s.hydrated);
  const ready = useAuthStore((s) => !!s.accessToken);

  const [cancelling, setCancelling] = useState(false);
  const [cancelDone, setCancelDone] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  // Wait for the store to hydrate from localStorage before deciding the user
  // is logged out — otherwise a hard reload always bounces to /login.
  useEffect(() => {
    if (hydrated && !ready) router.replace("/login");
  }, [hydrated, ready, router]);

  const { data: status, isLoading, refetch } = useQuery<SubscriptionStatus>({
    queryKey: ["billing-status"],
    queryFn: paymentsApi.status,
    enabled: ready,
  });

  async function handleCancel() {
    setCancelling(true);
    setCancelError(null);
    try {
      await paymentsApi.cancel("User requested cancellation from billing page");
      setCancelDone(true);
      setShowConfirm(false);
      refetch();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setCancelError(e?.message || "Cancellation failed. Please try again.");
    } finally {
      setCancelling(false);
    }
  }

  // While the store hydrates or the logout redirect is settling, show a
  // minimal branded loader instead of a dead black screen.
  if (!ready || !user) {
    return (
      <main className="grid min-h-dvh place-items-center bg-[#07080f] text-white/50">
        <div className="flex items-center gap-3 text-sm">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white/70" />
          {hydrated ? "Redirecting…" : "Loading your account…"}
        </div>
      </main>
    );
  }

  const creditsUsed = status ? status.credits_per_day - status.credits_remaining : 0;
  const periodEnd = status?.current_period_end
    ? new Date(status.current_period_end).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;

  return (
    <WorkspaceShell title="Billing & Credits" eyebrow="Account">
        <div className="mx-auto max-w-4xl px-5 py-10 sm:px-8">
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((n) => (
                <div key={n} className="h-32 animate-pulse rounded-2xl bg-white/[.04]" />
              ))}
            </div>
          ) : status ? (
            <div className="space-y-6">
              {/* Current plan */}
              <motion.section
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.45 }}
                className={`relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br ${PLAN_COLORS[status.plan_id] || PLAN_COLORS.free} p-8`}
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[.18em] text-white/50">Current plan</p>
                    <h2 className="mt-2 text-3xl font-semibold text-white">{status.plan_name}</h2>
                    {status.subscription_status && (
                      <span
                        className={`mt-2 inline-block rounded-full border px-3 py-1 text-xs font-semibold capitalize ${STATUS_COLORS[status.subscription_status] || ""}`}
                      >
                        {status.subscription_status.replace("_", " ")}
                      </span>
                    )}
                    {periodEnd && (
                      <p className="mt-3 flex items-center gap-1.5 text-sm text-white/55">
                        <Calendar className="h-3.5 w-3.5" />
                        {status.subscription_status === "cancelled"
                          ? `Access until ${periodEnd}`
                          : `Renews ${periodEnd}`}
                      </p>
                    )}
                  </div>
                  {status.is_free && (
                    <Link
                      href="/pricing"
                      className="flex items-center gap-2 rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_8px_24px_rgba(79,124,255,.25)] transition hover:brightness-110"
                    >
                      Upgrade plan <ArrowUpRight className="h-4 w-4" />
                    </Link>
                  )}
                </div>
              </motion.section>

              {/* Credit usage */}
              <motion.section
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.45, delay: 0.08 }}
                className="rounded-3xl border border-white/10 bg-[#10121f] p-6"
              >
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4 text-cyan-300" />
                  <h3 className="font-semibold text-white">Daily Credits</h3>
                </div>
                <div className="mt-5 grid gap-5 sm:grid-cols-3">
                  <div className="rounded-2xl border border-white/[.07] bg-black/20 p-4">
                    <p className="text-xs text-white/45">Remaining today</p>
                    <p className="mt-1 text-2xl font-semibold text-white">
                      {status.credits_remaining.toLocaleString("en-IN")}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/[.07] bg-black/20 p-4">
                    <p className="text-xs text-white/45">Used today</p>
                    <p className="mt-1 text-2xl font-semibold text-white">
                      {creditsUsed.toLocaleString("en-IN")}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/[.07] bg-black/20 p-4">
                    <p className="text-xs text-white/45">Daily allowance</p>
                    <p className="mt-1 text-2xl font-semibold text-cyan-200">
                      {status.credits_per_day.toLocaleString("en-IN")}
                    </p>
                  </div>
                </div>
                <CreditBar used={creditsUsed} total={status.credits_per_day} />
                <p className="mt-2 text-xs text-white/35">
                  100 credits = 1 video processed. Credits reset daily at midnight.
                </p>
              </motion.section>

              {/* Upgrade section if on free */}
              {status.is_free && (
                <motion.section
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, delay: 0.12 }}
                  className="rounded-3xl border border-[#4f7cff]/20 bg-gradient-to-br from-[#151a35] to-[#0c0e1a] p-6"
                >
                  <h3 className="font-semibold text-white">Unlock more processing power</h3>
                  <p className="mt-1 text-sm text-white/55">
                    Upgrade to Starter or Pro for priority processing, higher daily credit limits, and longer output retention.
                  </p>
                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    {(["starter", "pro"] as const).map((pid) => (
                      <Link
                        key={pid}
                        href={`/checkout?plan=${pid}`}
                        className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/[.04] px-4 py-3.5 text-sm transition hover:border-[#4f7cff]/40 hover:bg-[#4f7cff]/10"
                      >
                        <span className="font-medium capitalize text-white">{pid}</span>
                        <span className="flex items-center gap-1 text-cyan-200">
                          View plan <ChevronRight className="h-4 w-4" />
                        </span>
                      </Link>
                    ))}
                  </div>
                </motion.section>
              )}

              {/* Cancel subscription */}
              {!status.is_free && status.subscription_status === "active" && (
                <motion.section
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, delay: 0.16 }}
                  className="rounded-3xl border border-white/10 bg-[#10121f] p-6"
                >
                  <h3 className="font-semibold text-white">Manage subscription</h3>
                  <p className="mt-1 text-sm text-white/55">
                    Cancelling will stop auto-renewal. You keep access until the end of the current billing period.
                  </p>

                  <AnimatePresence>
                    {cancelError && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mt-4 flex items-start gap-2 overflow-hidden rounded-xl border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-300"
                      >
                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                        {cancelError}
                      </motion.div>
                    )}
                    {cancelDone && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        className="mt-4 flex items-center gap-2 rounded-xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-300"
                      >
                        <Check className="h-4 w-4 shrink-0" />
                        Subscription cancelled. Your access continues until the billing period ends.
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {!cancelDone && (
                    <div className="mt-5">
                      {!showConfirm ? (
                        <button
                          onClick={() => setShowConfirm(true)}
                          className="rounded-xl border border-rose-400/20 bg-rose-400/10 px-4 py-2 text-sm font-medium text-rose-300 transition hover:bg-rose-400/20"
                        >
                          Cancel subscription
                        </button>
                      ) : (
                        <div className="rounded-2xl border border-rose-400/20 bg-rose-400/[.07] p-4">
                          <p className="text-sm font-medium text-rose-200">
                            Are you sure? You&apos;ll lose {status.plan_name} features at the end of your billing period.
                          </p>
                          <div className="mt-4 flex gap-3">
                            <button
                              onClick={handleCancel}
                              disabled={cancelling}
                              className="rounded-xl bg-rose-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-rose-600 disabled:opacity-60"
                            >
                              {cancelling ? "Cancelling…" : "Yes, cancel subscription"}
                            </button>
                            <button
                              onClick={() => setShowConfirm(false)}
                              className="rounded-xl border border-white/10 px-4 py-2 text-sm font-medium text-white/70 transition hover:text-white"
                            >
                              Keep my plan
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </motion.section>
              )}

              {/* Security note */}
              <div className="flex items-center gap-2 text-xs text-white/30">
                <Shield className="h-3.5 w-3.5" />
                Payments are processed by Razorpay. We do not store your card details.
              </div>
            </div>
          ) : null}
        </div>
    </WorkspaceShell>
  );
}
