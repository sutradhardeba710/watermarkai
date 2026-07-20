"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { Check, Info, ShieldCheck, Sparkles } from "lucide-react";

import { currencySymbol, videosPerDay, type PricingPlan } from "@/components/pricingPlans";
import { planTargetCopy } from "./content";
import { useLivePlans } from "./useLivePlans";
import { useMarketingAuth } from "./useMarketingAuth";
import { cn } from "@/lib/utils";

const money = (v: number) => `${currencySymbol}${v.toLocaleString("en-IN")}`;
const PLAN_ORDER: Record<string, number> = { free: 0, starter: 1, pro: 2 };

function ctaFor(plan: PricingPlan, isAuthed: boolean, currentPlanId: string | null) {
  if (isAuthed && currentPlanId) {
    if (plan.id === currentPlanId) return { label: "Current plan", href: null as string | null, disabled: true };
    const higher = (PLAN_ORDER[plan.id] ?? 0) > (PLAN_ORDER[currentPlanId] ?? 0);
    if (higher) {
      return { label: `Upgrade to ${plan.name}`, href: plan.id === "free" ? "/signup" : `/checkout?plan=${plan.id}`, disabled: false };
    }
    return { label: `Switch to ${plan.name}`, href: `/checkout?plan=${plan.id}`, disabled: false };
  }
  if (plan.id === "free") return { label: "Start free", href: "/signup", disabled: false };
  if (plan.id === "starter") return { label: "Choose Starter", href: "/checkout?plan=starter", disabled: false };
  if (plan.id === "pro") return { label: "Choose Pro", href: "/checkout?plan=pro", disabled: false };
  return { label: `Choose ${plan.name}`, href: `/checkout?plan=${plan.id}`, disabled: false };
}

export function PricingCard({
  plan,
  index,
  isAuthed,
  currentPlanId,
}: {
  plan: PricingPlan;
  index: number;
  isAuthed: boolean;
  currentPlanId: string | null;
}) {
  const reduce = useReducedMotion();
  const videos = videosPerDay(plan);
  const cta = ctaFor(plan, isAuthed, currentPlanId);

  const specs = [
    [`${plan.creditsPerDay.toLocaleString("en-IN")} credits/day`, `~ ${videos} videos/day`],
    ["Processing speed", plan.speed],
    ["Batch processing", plan.batch],
    ["Retention", plan.retention],
    ["Support", plan.support],
  ];

  return (
    <motion.article
      initial={reduce ? { opacity: 1 } : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: reduce ? 0 : 0.45, delay: reduce ? 0 : index * 0.08, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "relative flex h-full flex-col rounded-3xl border p-7",
        plan.popular
          ? "border-[#6d5ef7]/80 bg-gradient-to-b from-[#221d4d] via-[#171735] to-[#10121f] shadow-[0_24px_90px_rgba(109,94,247,.3)] ring-1 ring-[#8b5cf6]/40"
          : "border-white/[.08] bg-gradient-to-b from-white/[.04] to-white/[.01] transition hover:border-white/[.16]",
      )}
    >
      {plan.popular && (
        <span className="absolute -top-3 left-6 inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#a855f7] px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-white shadow-[0_4px_16px_rgba(139,92,246,.5)]">
          <Sparkles className="h-3 w-3" /> Most popular
        </span>
      )}

      <p className="text-sm font-semibold text-cyan-200">{plan.name}</p>
      <p className="mt-1 min-h-[2.5rem] text-sm leading-6 text-white/50">{planTargetCopy[plan.id] ?? plan.description}</p>

      <div className="mt-4 flex flex-wrap items-baseline gap-x-2">
        <span className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">{money(plan.promoPrice ?? plan.price)}</span>
        <span className="text-sm text-white/45">/month</span>
      </div>
      {plan.price === 0 ? (
        <p className="mt-2 text-xs text-white/50">Free. No card required.</p>
      ) : (
        <p className="mt-2 text-xs text-white/50">Billed monthly. Cancel anytime.</p>
      )}

      <dl className="mt-6 space-y-2.5 border-t border-white/[.07] pt-5 text-sm">
        {specs.map(([label, value]) => (
          <div key={label} className="flex items-start justify-between gap-3">
            <dt className="text-white/45">{label}</dt>
            <dd className="text-right font-medium text-white/80">{value}</dd>
          </div>
        ))}
      </dl>

      <ul className="mt-5 flex-1 space-y-2.5 text-sm text-white/75">
        {plan.features.map((feature) => (
          <li key={feature} className="flex gap-2">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-cyan-200" />
            {feature}
          </li>
        ))}
      </ul>

      {cta.disabled || !cta.href ? (
        <span
          aria-disabled="true"
          className="mt-7 inline-flex items-center justify-center gap-2 rounded-full border border-white/10 bg-white/[.03] px-5 py-3.5 text-center text-sm font-semibold text-white/40"
        >
          <ShieldCheck className="h-4 w-4" /> {cta.label}
        </span>
      ) : (
        <Link
          href={cta.href}
          className={cn(
            "mt-7 block rounded-full px-5 py-3.5 text-center text-sm font-semibold transition focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300",
            plan.popular
              ? "bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] text-white hover:brightness-110"
              : "border border-white/15 text-white hover:bg-white/[.06]",
          )}
        >
          {cta.label}
        </Link>
      )}
    </motion.article>
  );
}

function CreditsExplanation() {
  const items: [string, string][] = [
    ["What is a credit?", "A credit is the unit ClearFrame uses for processing. 100 credits equals one full-video render."],
    ["Do previews cost credits?", "No. Generating a short preview is free. Credits are only used for a full render."],
    ["What if processing fails?", "Credits for a failed render are returned to your balance automatically."],
    ["When do credits reset?", "Daily credits reset every 24 hours and do not roll over."],
    ["After cancellation?", "You keep access until the end of the current billing period, then move to Free."],
  ];
  return (
    <div className="mt-12 rounded-3xl border border-white/10 bg-[#0c0e1a] p-6 sm:p-8">
      <div className="flex items-center gap-2">
        <Info className="h-4 w-4 text-cyan-200" />
        <h3 className="text-lg font-semibold text-white">How credits work</h3>
      </div>
      <div className="mt-5 grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        {items.map(([q, a]) => (
          <div key={q}>
            <p className="text-sm font-semibold text-white/85">{q}</p>
            <p className="mt-1 text-sm leading-6 text-white/55">{a}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PricingSection() {
  const { plans, state } = useLivePlans();
  const { isAuthed, currentPlanId } = useMarketingAuth();
  const isDev = process.env.NODE_ENV !== "production";

  return (
    <section id="pricing" className="scroll-mt-24 bg-[#07080f] py-24 sm:py-28">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <div className="mx-auto max-w-2xl text-center">
          <p className="bg-gradient-to-r from-[#7de6f7] to-[#9db9ff] bg-clip-text text-xs font-semibold uppercase tracking-[.18em] text-transparent">Pricing</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-.03em] text-white sm:text-5xl">Simple plans based on how much you process.</h2>
          <p className="mt-5 leading-7 text-white/60">Start free, then move to a plan that fits your video workload.</p>
        </div>

        {state === "fallback" && (
          <p className="mx-auto mt-6 max-w-xl rounded-xl border border-amber-400/20 bg-amber-400/10 px-4 py-2.5 text-center text-xs text-amber-100">
            Showing standard pricing. Live plan details will refresh automatically.
          </p>
        )}

        <div className="mt-10 grid gap-5 lg:grid-cols-3">
          {plans.map((plan, i) => (
            <PricingCard key={plan.id} plan={plan} index={i} isAuthed={isAuthed} currentPlanId={currentPlanId} />
          ))}
        </div>
        {state === "loading" && (
          <p className="mt-4 text-center text-xs text-white/35" aria-live="polite">Refreshing live plan details…</p>
        )}

        <CreditsExplanation />

        <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-white/50">
          <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-cyan-200" /> Secure Razorpay checkout</span>
          <span className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-cyan-200" /> Cancel anytime from billing settings</span>
          <span className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-cyan-200" /> No hidden processing charges</span>
          {isDev && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/20 bg-amber-400/10 px-2.5 py-1 text-amber-100">
              Sandbox billing (development)
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
