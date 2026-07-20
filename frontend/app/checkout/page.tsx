"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { Check, ChevronLeft, Lock, Shield, Sparkles, Zap, AlertCircle } from "lucide-react";
import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { useAuthStore } from "@/features/auth/authStore";
import { paymentsApi } from "@/services/payments";

// Static presentation defaults (colors, features). Price/credits are
// overridden with live DB values from GET /plans so admin edits apply.
// NOTE: no client-side "intro price" — the backend is the source of truth
// for every amount shown; discounts come from promo codes via the server.
const PLAN_META = {
  starter: {
    id: "starter",
    name: "Starter",
    price: 4099,
    creditsPerDay: 1000,
    color: "from-[#4f7cff] to-[#6d5ef7]",
    features: [
      "1,000 credits / day (~10 videos/day)",
      "Priority processing queue",
      "Longer output retention",
      "Email support",
      "AI detection + manual mask control",
      "Original audio & resolution preserved",
    ],
  },
  pro: {
    id: "pro",
    name: "Pro",
    price: 16799,
    creditsPerDay: 2000,
    color: "from-[#6d5ef7] to-[#22d3ee]",
    features: [
      "2,000 credits / day (~20 videos/day)",
      "Fastest processing lane",
      "Batch processing",
      "Priority support",
      "Configurable output retention",
      "Everything in Starter",
    ],
  },
} as const;

type PlanId = keyof typeof PLAN_META;

type PlanInfo = {
  id: string;
  name: string;
  price: number;
  creditsPerDay: number;
  color: string;
  features: readonly string[];
};

/** Merge live DB plan values (price/credits/name) over the static defaults. */
function useLivePlanMeta(planId: PlanId): PlanInfo {
  const [plan, setPlan] = useState<PlanInfo>(PLAN_META[planId]);
  useEffect(() => {
    let cancelled = false;
    setPlan(PLAN_META[planId]);
    paymentsApi
      .plans()
      .then((live) => {
        if (cancelled) return;
        const row = live.find((p) => p.id === planId);
        if (!row) return;
        setPlan((base) => ({
          ...base,
          name: row.name || base.name,
          price: Math.round(row.price_inr / 100),
          creditsPerDay: row.credits_per_day,
        }));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [planId]);
  return plan;
}

declare global {
  interface Window {
    Razorpay: new (opts: Record<string, unknown>) => { open(): void };
  }
}

function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window === "undefined") return resolve(false);
    if (window.Razorpay) return resolve(true);
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

function PlanSummaryCard({ planId }: { planId: PlanId }) {
  const plan = useLivePlanMeta(planId);
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-3xl border border-white/10 bg-[#10121f] p-8"
    >
      <div className="flex items-center gap-3">
        <span
          className={`grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br ${plan.color} text-white shadow-lg`}
        >
          <Sparkles className="h-5 w-5" />
        </span>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.18em] text-white/50">
            ClearFrame
          </p>
          <p className="font-semibold text-white">{plan.name} Plan</p>
        </div>
      </div>

      <div className="mt-8 flex items-baseline gap-3">
        <span className="text-5xl font-semibold tracking-tight text-white">
          ₹{plan.price.toLocaleString("en-IN")}
        </span>
        <span className="text-sm text-white/50">/month</span>
      </div>

      <p className="mt-2 text-xs text-white/45">
        Billed monthly — cancel anytime. Have a promo code? Apply it at checkout.
      </p>

      <div className="my-7 h-px bg-white/[.07]" />

      <p className="mb-4 text-xs font-semibold uppercase tracking-[.14em] text-white/45">
        Included in this plan
      </p>
      <ul className="space-y-3">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2.5 text-sm text-white/75">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-cyan-300" />
            {f}
          </li>
        ))}
      </ul>

      <div className="mt-7 flex items-center gap-2 rounded-2xl border border-white/[.07] bg-white/[.03] p-3 text-xs text-white/45">
        <Shield className="h-4 w-4 shrink-0 text-white/30" />
        Secured by Razorpay · 256-bit encryption · Cancel anytime
      </div>
    </motion.div>
  );
}

function CheckoutForm({
  planId,
  userEmail,
  userName,
}: {
  planId: PlanId;
  userEmail: string;
  userName: string;
}) {
  const plan = useLivePlanMeta(planId);
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sandboxMode, setSandboxMode] = useState(false);
  
  const [promoInput, setPromoInput] = useState("");
  const [appliedPromo, setAppliedPromo] = useState<{
    code: string;
    discount: number;
    finalAmount: number;
    discountAmount: number;
  } | null>(null);
  const [promoBusy, setPromoBusy] = useState(false);
  const [promoError, setPromoError] = useState<string | null>(null);

  // Server-authoritative amount: the plan price, or the promo-validated final
  // amount from the backend. Never computed client-side.
  const dueToday = appliedPromo ? appliedPromo.finalAmount : plan.price;

  async function handleApplyPromo() {
    if (!promoInput.trim()) return;
    setPromoError(null);
    setPromoBusy(true);
    try {
      const res = await paymentsApi.validatePromo(promoInput.trim(), planId);
      if (res.valid && res.final_amount !== null) {
        setAppliedPromo({
          code: promoInput.trim(),
          discount: res.discount_percent ?? 0,
          finalAmount: res.final_amount,
          discountAmount: res.discount_amount ?? 0,
        });
        setPromoInput("");
      } else {
        setPromoError(res.message || "Invalid promo code");
      }
    } catch (e: any) {
      setPromoError("Failed to validate promo code");
    } finally {
      setPromoBusy(false);
    }
  }

  async function handleCheckout() {
    setError(null);
    setBusy(true);

    try {
      // 1. Create subscription on backend
      const sub = await paymentsApi.subscribe(planId, appliedPromo?.code);

      // 2. Sandbox mode — backend returned a fake sub ID (no Razorpay creds)
      if (sub.razorpay_key_id === "rzp_test_sandbox") {
        setSandboxMode(true);
        // In sandbox, the backend already upgraded the user. Redirect after a moment.
        setTimeout(() => router.replace("/dashboard?subscribed=1"), 1500);
        return;
      }

      // 3. Load Razorpay checkout script
      const loaded = await loadRazorpayScript();
      if (!loaded) {
        setError("Could not load Razorpay checkout. Please check your connection.");
        setBusy(false); // re-enable the pay button so the user can retry
        return;
      }

      // 4. Open Razorpay modal
      const options: Record<string, unknown> = {
        key: sub.razorpay_key_id,
        subscription_id: sub.razorpay_subscription_id,
        name: "ClearFrame",
        description: `${plan.name} Plan — Monthly Subscription`,
        prefill: {
          name: userName,
          email: userEmail,
        },
        theme: { color: "#4f7cff" },
        modal: {
          ondismiss: () => {
            setBusy(false);
          },
        },
        handler: (_response: Record<string, string>) => {
          // Payment succeeded — webhook will confirm on backend.
          // Redirect to dashboard with success param.
          router.replace("/dashboard?subscribed=1");
        },
      };

      const rz = new window.Razorpay(options);
      rz.open();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(
        e?.message ||
          "Something went wrong. Please try again or contact support."
      );
      setBusy(false);
    }
  }

  if (sandboxMode) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        className="rounded-3xl border border-cyan-300/20 bg-cyan-300/10 p-8 text-center"
      >
        <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-cyan-300/20">
          <Check className="h-7 w-7 text-cyan-300" />
        </div>
        <h3 className="text-xl font-semibold text-white">Sandbox activated!</h3>
        <p className="mt-2 text-sm text-white/60">
          Razorpay is in sandbox mode (no credentials configured). Your plan has been
          upgraded — redirecting to dashboard…
        </p>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-3xl border border-white/10 bg-[#10121f] p-8"
    >
      <h2 className="text-2xl font-semibold text-white">Complete your subscription</h2>
      <p className="mt-2 text-sm text-white/55">
        You&apos;ll be redirected to Razorpay&apos;s secure checkout to complete your payment.
      </p>

      <div className="mt-8 space-y-4 rounded-2xl border border-white/[.07] bg-black/20 p-5">
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/55">Plan</span>
          <span className="font-medium text-white">{plan.name}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-white/55">Monthly price</span>
          <span className={appliedPromo ? "text-white/30 line-through" : "font-medium text-white"}>
            ₹{plan.price.toLocaleString("en-IN")}/mo
          </span>
        </div>
        {appliedPromo && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-white/55">Promo discount</span>
            <span className="font-medium text-emerald-400">
              −₹{appliedPromo.discountAmount.toLocaleString("en-IN")}
            </span>
          </div>
        )}
        
        {/* Promo Code Input */}
        <div className="mt-4 border-t border-white/[.07] pt-4">
          {!appliedPromo ? (
            <div className="flex items-start gap-2">
              <div className="flex-1">
                <input
                  type="text"
                  placeholder="Promo code"
                  value={promoInput}
                  onChange={(e) => setPromoInput(e.target.value.toUpperCase())}
                  className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white placeholder-white/30 focus:border-cyan-300 focus:outline-none"
                />
                {promoError && <p className="mt-1 text-xs text-rose-400">{promoError}</p>}
              </div>
              <button
                onClick={handleApplyPromo}
                disabled={promoBusy || !promoInput.trim()}
                className="rounded-lg bg-white/10 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/20 disabled:opacity-50"
              >
                {promoBusy ? "..." : "Apply"}
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-lg bg-emerald-500/10 px-3 py-2 border border-emerald-500/20">
              <div className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" />
                <span className="text-sm font-medium text-emerald-400">{appliedPromo.code} applied</span>
              </div>
              <button
                onClick={() => setAppliedPromo(null)}
                className="text-xs text-white/40 hover:text-white"
              >
                Remove
              </button>
            </div>
          )}
        </div>

        <div className="h-px bg-white/[.07] mt-4" />
        <div className="flex items-center justify-between pt-4">
          <span className="text-sm text-white/55">Due today</span>
          <div className="text-right">
            <span className="text-xl font-semibold text-white">₹{dueToday.toLocaleString("en-IN")}</span>
            {appliedPromo && (
              <p className="text-xs text-emerald-400">{appliedPromo.discount}% off standard price</p>
            )}
          </div>
        </div>
      </div>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-4 flex items-start gap-2 overflow-hidden rounded-xl border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-300"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      <button
        onClick={handleCheckout}
        disabled={busy}
        className={`mt-6 flex w-full items-center justify-center gap-2.5 rounded-full bg-gradient-to-r ${plan.color} px-6 py-4 font-semibold text-white shadow-[0_12px_40px_rgba(79,124,255,.3)] transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:cursor-not-allowed disabled:opacity-60`}
      >
        {busy ? (
          <>
            <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Opening checkout…
          </>
        ) : (
          <>
            <Lock className="h-4 w-4" />
            Pay ₹{dueToday.toLocaleString("en-IN")} with Razorpay
          </>
        )}
      </button>

      <p className="mt-4 text-center text-xs text-white/35">
        By proceeding you agree to our Terms of Service. You can cancel anytime from your account.
      </p>

      <div className="mt-6 flex items-center justify-center gap-4 text-xs text-white/30">
        <span className="flex items-center gap-1.5">
          <Shield className="h-3.5 w-3.5" /> SSL secured
        </span>
        <span className="flex items-center gap-1.5">
          <Zap className="h-3.5 w-3.5" /> Instant activation
        </span>
        <span className="flex items-center gap-1.5">
          <Check className="h-3.5 w-3.5" /> Cancel anytime
        </span>
      </div>
    </motion.div>
  );
}

function CheckoutPageInner() {
  useHydrateAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const user = useAuthStore((s) => s.user);
  const hydrated = useAuthStore((s) => s.hydrated);
  const ready = useAuthStore((s) => !!s.accessToken);

  const rawPlan = searchParams.get("plan") ?? "";
  const planId: PlanId | null = rawPlan === "starter" || rawPlan === "pro" ? rawPlan : null;

  // Redirect if not logged in — but only after the store has hydrated from
  // localStorage, or a hard reload always bounces a logged-in user to /login.
  useEffect(() => {
    if (hydrated && !ready) {
      const redirect = encodeURIComponent(`/checkout?plan=${rawPlan}`);
      router.replace(`/login?redirect=${redirect}`);
    }
  }, [hydrated, ready, rawPlan, router]);

  // Redirect if invalid plan
  useEffect(() => {
    if (ready && !planId) {
      router.replace("/pricing");
    }
  }, [ready, planId, router]);

  if (!ready || !user || !planId) return null;

  return (
    <main className="min-h-screen bg-[#07080f] text-[#f5f6fa]">
      {/* Top bar */}
      <header className="border-b border-white/[.07] bg-[#07080f]/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <Link
            href="/pricing"
            className="flex items-center gap-2 text-sm text-white/55 transition hover:text-white"
          >
            <ChevronLeft className="h-4 w-4" />
            Back to pricing
          </Link>
          <span className="flex items-center gap-2 text-sm font-semibold text-white">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] text-white">
              <Sparkles className="h-4 w-4" />
            </span>
            ClearFrame Checkout
          </span>
          <div className="flex items-center gap-1.5 text-xs text-white/35">
            <Lock className="h-3.5 w-3.5" />
            Secured
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8 lg:py-20">
        {/* Heading */}
        <div className="mb-12 text-center">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="text-xs font-semibold uppercase tracking-[.18em] text-cyan-200"
          >
            Complete your upgrade
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.06 }}
            className="mt-3 text-4xl font-semibold tracking-tight text-white sm:text-5xl"
          >
            You&apos;re one step away from{" "}
            <span className="bg-gradient-to-r from-[#4f7cff] to-[#22d3ee] bg-clip-text text-transparent">
              {PLAN_META[planId].name}
            </span>
          </motion.h1>
        </div>

        {/* Two-column layout */}
        <div className="grid gap-8 lg:grid-cols-[1fr_1fr]">
          <PlanSummaryCard planId={planId} />
          <CheckoutForm
            planId={planId}
            userEmail={user.email ?? ""}
            userName={user.full_name ?? ""}
          />
        </div>
      </div>
    </main>
  );
}

// useSearchParams() requires a Suspense boundary for static prerender
// (nextjs.org/docs/messages/missing-suspense-with-csr-bailout).
export default function CheckoutPage() {
  return (
    <Suspense>
      <CheckoutPageInner />
    </Suspense>
  );
}
