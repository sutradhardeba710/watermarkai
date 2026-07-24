"use client";

import Link from "next/link";
import { Check, CircleAlert, Coins, Gauge, Info, Minus, RefreshCcw, ShieldCheck, WalletCards } from "lucide-react";

import { creditPolicy, creditsPerJob, currencySymbol, jobsPerDay, type PricingPlan } from "./pricingPlans";
import { useMarketingAuth } from "./marketing/useMarketingAuth";
import { useLivePlans } from "./marketing/useLivePlans";

const PLAN_ORDER: Record<string, number> = { free: 0, starter: 1, pro: 2 };
const money = (value: number) => `${currencySymbol}${value.toLocaleString("en-IN")}`;
const duration = (seconds: number | null) => seconds === null ? "Platform managed" : seconds % 60 === 0 ? `${seconds / 60} minutes` : `${seconds} seconds`;
const upload = (mb: number | null) => mb === null ? "Platform managed" : `${mb.toLocaleString("en-IN")} MB`;

function ctaFor(plan: PricingPlan, isAuthed: boolean, currentPlanId: string | null) {
  if (isAuthed && currentPlanId) {
    if (plan.id === currentPlanId) return { label: "Current plan", href: null };
    if (plan.id === "free") return { label: "Included with your account", href: null };
    const higher = (PLAN_ORDER[plan.id] ?? 0) > (PLAN_ORDER[currentPlanId] ?? 0);
    return { label: `${higher ? "Upgrade" : "Switch"} to ${plan.name}`, href: `/checkout?plan=${plan.id}` };
  }
  if (isAuthed) return plan.id === "free" ? { label: "Open dashboard", href: "/dashboard" } : { label: `Choose ${plan.name}`, href: `/checkout?plan=${plan.id}` };
  return plan.id === "free" ? { label: "Create a free account", href: "/signup" } : { label: `Choose ${plan.name}`, href: `/checkout?plan=${plan.id}` };
}

function PlanCard({ plan, isAuthed, currentPlanId }: { plan: PricingPlan; isAuthed: boolean; currentPlanId: string | null }) {
  const cta = ctaFor(plan, isAuthed, currentPlanId);
  return <article className={`relative flex h-full flex-col rounded-3xl border p-7 ${plan.popular ? "border-[#6d5ef7] bg-gradient-to-b from-[#1b1b3a] to-[#10121f] shadow-[0_22px_70px_rgba(79,124,255,.2)] ring-1 ring-[#4f7cff]/35" : "border-white/10 bg-[#10121f]"}`}>{plan.popular && <span className="absolute -top-3 left-6 rounded-full bg-gradient-to-r from-[#4f7cff] to-[#8b5cf6] px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-white">Most popular</span>}<div className="flex items-center justify-between gap-3"><p className="text-sm font-semibold text-cyan-100">{plan.name}</p><span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] capitalize text-white/40">{plan.billingInterval}</span></div><div className="mt-5 flex items-baseline gap-2"><span className="text-4xl font-semibold tracking-[-.04em] text-white sm:text-5xl">{money(plan.price)}</span><span className="text-sm text-white/40">/{plan.billingInterval === "monthly" ? "month" : plan.billingInterval}</span></div><p className="mt-2 text-xs text-white/45">{plan.price === 0 ? "No card required." : "Secure checkout powered by Razorpay."}</p><div className="mt-7 rounded-2xl border border-white/10 bg-black/15 p-4"><p className="text-2xl font-semibold text-white">{plan.creditsPerDay.toLocaleString("en-IN")} credits/day</p><p className="mt-1 text-sm text-cyan-100">Up to {jobsPerDay(plan)} full jobs per daily allowance</p><p className="mt-2 text-xs text-white/40">Quick previews are free</p></div><p className="mt-5 min-h-12 text-sm leading-6 text-white/58">{plan.description}</p><ul className="mt-5 flex-1 space-y-3 text-sm text-white/70">{plan.features.map((feature) => <li key={feature} className="flex gap-2"><Check size={16} className="mt-0.5 shrink-0 text-cyan-100" />{feature}</li>)}</ul>{cta.href ? <Link href={cta.href} className={`mt-7 inline-flex min-h-12 items-center justify-center rounded-full px-5 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${plan.popular ? "bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] text-white hover:brightness-110" : "border border-white/15 text-white hover:bg-white/[.06]"}`}>{cta.label}</Link> : <span aria-disabled="true" className="mt-7 inline-flex min-h-12 items-center justify-center gap-2 rounded-full border border-white/10 bg-white/[.03] px-5 text-sm font-semibold text-white/40"><ShieldCheck size={16} />{cta.label}</span>}</article>;
}

function PricingCardsLoading() {
  return <div className="mt-12 grid gap-5 lg:grid-cols-3" aria-busy="true" aria-label="Loading current plan prices">{Array.from({ length: 3 }, (_, index) => <div key={index} className="h-[34rem] animate-pulse rounded-3xl border border-white/10 bg-[#10121f] p-7"><div className="h-4 w-20 rounded bg-white/10" /><div className="mt-6 h-12 w-36 rounded bg-white/10" /><div className="mt-3 h-3 w-28 rounded bg-white/[.07]" /><div className="mt-7 h-28 rounded-2xl bg-white/[.06]" /><div className="mt-6 space-y-4"><div className="h-3 w-full rounded bg-white/[.07]" /><div className="h-3 w-5/6 rounded bg-white/[.07]" /><div className="h-3 w-3/4 rounded bg-white/[.07]" /></div><div className="mt-12 h-12 rounded-full bg-white/[.07]" /></div>)}</div>;
}
function CreditExplainer() {
  const cards = [
    { title: "Quick preview", value: "Free", body: "Generate and compare a short preview without a credit deduction.", icon: Gauge },
    { title: "Full processing", value: `${creditsPerJob} credits`, body: "The server deducts the job cost immediately before queue dispatch.", icon: Coins },
    { title: "Failed jobs", value: "Refunded", body: "The failure path returns the job cost through the immutable credit ledger.", icon: RefreshCcw },
    { title: "Daily reset", value: "Scheduled", body: "Credits reset to the active plan allowance and do not roll over.", icon: WalletCards },
  ];
  return <section aria-labelledby="credits-title" className="mt-16 rounded-[2rem] border border-white/10 bg-[#0c0e1a] p-6 sm:p-9"><div className="grid gap-8 lg:grid-cols-[.7fr_1.3fr]"><div><p className="text-xs font-semibold uppercase tracking-[.18em] text-cyan-100">How credits work</p><h3 id="credits-title" className="mt-4 text-3xl font-semibold tracking-[-.04em] text-white sm:text-4xl">Know the cost before the full job.</h3><p className="mt-4 leading-7 text-white/55">{creditPolicy.fullJobCopy} {creditPolicy.previewCopy} Credit balance and plan state are shown inside the authenticated workflow.</p></div><div className="grid gap-3 sm:grid-cols-2">{cards.map(({ title, value, body, icon: Icon }) => <article key={title} className="rounded-2xl border border-white/10 bg-white/[.03] p-5"><Icon size={18} className="text-cyan-100" /><p className="mt-4 text-xs uppercase tracking-wider text-white/35">{title}</p><p className="mt-1 text-xl font-semibold text-white">{value}</p><p className="mt-2 text-xs leading-5 text-white/45">{body}</p></article>)}</div></div><div className="mt-7 grid gap-3 border-t border-white/10 pt-7 sm:grid-cols-3">{[["Promo codes", "Eligibility and the final amount are validated by the server before checkout."], ["Cancellation", "Cancel from Billing; the payment service returns the subscription result."], ["Plan changes", "Authenticated CTAs show the current plan and the correct upgrade or switch path."]].map(([title, body]) => <div key={title} className="flex gap-3"><Info size={16} className="mt-0.5 shrink-0 text-cyan-100" /><p className="text-sm leading-6 text-white/50"><span className="font-semibold text-white/75">{title}.</span> {body}</p></div>)}</div></section>;
}

function CompareTable({ plans }: { plans: PricingPlan[] }) {
  const rows: Array<[string, (plan: PricingPlan) => string]> = [
    ["Credits / day", (plan) => plan.creditsPerDay.toLocaleString("en-IN")],
    ["Full jobs / allowance", (plan) => String(jobsPerDay(plan))],
    ["Maximum upload", (plan) => upload(plan.maxUploadMb)],
    ["Maximum duration", (plan) => duration(plan.maxDurationSeconds)],
    ["Maximum resolution", (plan) => plan.maxResolution ?? "Platform managed"],
    ["Concurrent jobs", (plan) => plan.concurrentJobs === null ? "Platform managed" : String(plan.concurrentJobs)],
    ["Processing lane", (plan) => plan.speed],
    ["Processing modes", (plan) => plan.processingModes],
    ["Retention", (plan) => plan.retention],
    ["Support", (plan) => plan.support],
  ];
  return (
    <section aria-labelledby="compare-plans-title" className="mt-16">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.18em] text-cyan-100">Plan comparison</p>
          <h3 id="compare-plans-title" className="mt-3 text-3xl font-semibold tracking-[-.04em] text-white">Limits stay connected to live plan data.</h3>
        </div>
        <p className="max-w-md text-sm leading-6 text-white/45">When a plan-specific value is unset, the comparison shows the actual platform default or identifies the limit as platform-managed.</p>
      </div>
      <div className="mt-8 grid gap-4 md:hidden">
        {plans.map((plan) => (
          <article key={plan.id} className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
            <div className="flex items-center justify-between gap-3">
              <h4 className="text-lg font-semibold text-white">{plan.name}</h4>
              {plan.popular && <span className="rounded-full bg-[#6d5ef7]/20 px-2.5 py-1 text-xs font-semibold text-[#c4b0ff]">Most popular</span>}
            </div>
            <dl className="mt-4 divide-y divide-white/[.07]">
              {rows.map(([label, value]) => (
                <div key={label} className="grid grid-cols-2 gap-4 py-3 text-sm">
                  <dt className="text-white/50">{label}</dt>
                  <dd className="text-right font-medium text-white/80">{value(plan) || <Minus size={15} className="ml-auto text-white/25" />}</dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </div>
      <div className="mt-8 hidden overflow-x-auto rounded-3xl border border-white/10 bg-[#10121f] md:block" role="region" aria-label="Scrollable plan comparison" tabIndex={0}>
        <table className="w-full min-w-[820px] text-left text-sm">
          <caption className="sr-only">ClearFrame plan prices and limits</caption>
          <thead><tr className="border-b border-white/10"><th className="sticky left-0 z-10 bg-[#10121f] px-5 py-4 text-xs uppercase tracking-wider text-white/35">Compare plans</th>{plans.map((plan) => <th key={plan.id} className="px-5 py-4 font-semibold text-white">{plan.name}</th>)}</tr></thead>
          <tbody>{rows.map(([label, value]) => <tr key={label} className="border-b border-white/[.07] last:border-0"><th className="sticky left-0 z-10 bg-[#10121f] px-5 py-4 font-medium text-white/55">{label}</th>{plans.map((plan) => <td key={plan.id} className="px-5 py-4 text-white/75">{value(plan) || <Minus size={15} className="text-white/25" />}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}
function PricingFAQ() {
  const items = [
    ["Does a preview consume credits?", "No. The current quick-preview endpoint does not deduct credits."],
    ["What consumes credits?", "Starting a full processing job costs 100 credits. Detection, masking, and quick preview do not deduct that job cost."],
    ["What happens if queue dispatch or processing fails?", creditPolicy.failureCopy],
    ["When do credits reset?", creditPolicy.resetCopy],
    ["How do promo codes work?", "The server validates eligibility, plan scope, dates, usage limits, and the final amount before payment."],
    ["What happens after cancellation?", "The billing page submits cancellation through the payment service and shows the resulting subscription status."],
  ];
  return <section aria-labelledby="pricing-faq-title" className="mx-auto mt-16 max-w-3xl"><h3 id="pricing-faq-title" className="text-3xl font-semibold tracking-[-.04em] text-white">Pricing questions, answered.</h3><div className="mt-7 divide-y divide-white/10 border-y border-white/10">{items.map(([question, answer]) => <details key={question} className="group"><summary className="flex min-h-16 cursor-pointer list-none items-center justify-between gap-4 font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-cyan-300"><span>{question}</span><span aria-hidden="true" className="text-xl text-cyan-100 transition-transform group-open:rotate-45">+</span></summary><p className="pb-6 pr-8 leading-7 text-white/55">{answer}</p></details>)}</div></section>;
}

export default function Pricing({ compact = false }: { compact?: boolean }) {
  const { plans, state } = useLivePlans();
  const { isAuthed, currentPlanId } = useMarketingAuth();
  return <section id="pricing" className="scroll-mt-24 bg-[#07080f] py-24 sm:py-32"><div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10"><div className="mx-auto max-w-3xl text-center"><p className="text-xs font-semibold uppercase tracking-[.18em] text-cyan-100">Pricing</p><h2 className="mt-4 text-4xl font-semibold tracking-[-.045em] text-white sm:text-5xl">Clear prices. Visible capacity. Free previews.</h2><p className="mt-5 leading-7 text-white/55">Free, Starter, and Pro use the same review-first workflow. The live Plan API supplies prices, daily credits, billing intervals, and configured limits.</p>{state === "fallback" && <p className="mt-4 inline-flex items-center gap-2 rounded-full border border-amber-300/20 bg-amber-300/[.06] px-3 py-2 text-xs text-amber-100"><CircleAlert size={14} /> Live plans are unavailable; standard plan values are shown.</p>}</div>{state === "loading" ? <PricingCardsLoading /> : <div className="mt-12 grid gap-5 lg:grid-cols-3">{plans.map((plan) => <PlanCard key={plan.id} plan={plan} isAuthed={isAuthed} currentPlanId={currentPlanId} />)}</div>}{!compact && <><CreditExplainer />{state !== "loading" && <CompareTable plans={plans} />}<PricingFAQ /><p className="mt-10 text-center text-xs text-white/35">Paid checkout uses Razorpay only when payment credentials are configured. Sandbox promo codes are never listed here.</p></>}</div></section>;
}
