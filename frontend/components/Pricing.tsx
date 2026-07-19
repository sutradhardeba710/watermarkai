"use client";

import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Check, Minus, Video, Zap } from "lucide-react";
import { useState } from "react";
import {
  creditPolicy,
  creditsPerVideo,
  currencySymbol,
  pricingPlans,
  videosPerDay,
  type PricingPlan,
} from "./pricingPlans";

const formatMoney = (value: number) => `${currencySymbol}${value.toLocaleString("en-IN")}`;

function CreditsInfo() {
  return (
    <div className="mt-10 grid gap-3 sm:grid-cols-3">
      <div className="rounded-2xl border border-white/10 bg-white/[.04] p-4">
        <Video className="text-cyan-200" size={18} />
        <p className="mt-3 font-semibold text-white">{creditPolicy.unitCopy}</p>
        <p className="mt-1 text-xs text-white/50">A simple unit for every processed video.</p>
      </div>
      <div className="rounded-2xl border border-white/10 bg-white/[.04] p-4">
        <Zap className="text-cyan-200" size={18} />
        <p className="mt-3 font-semibold text-white">Daily allowance</p>
        <p className="mt-1 text-xs text-white/50">{creditPolicy.resetCopy}</p>
      </div>
      <div className="rounded-2xl border border-white/10 bg-white/[.04] p-4">
        <Check className="text-cyan-200" size={18} />
        <p className="mt-3 font-semibold text-white">Only pay for processing</p>
        <p className="mt-1 text-xs text-white/50">Free has no credit card requirement.</p>
      </div>
    </div>
  );
}

function PricingCard({ plan, index }: { plan: PricingPlan; index: number }) {
  const videos = videosPerDay(plan);
  const href = plan.id === "free" ? "/signup" : `/signup?plan=${plan.id}`;
  const reduce = useReducedMotion();
  const displayPrice = plan.promoPrice ?? plan.price;

  return (
    <motion.article
      initial={reduce ? { opacity: 1 } : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: reduce ? 0 : 0.45, delay: reduce ? 0 : index * 0.08, ease: [0.22, 1, 0.36, 1] }}
      whileHover={reduce ? undefined : { y: -6 }}
      className={`relative flex h-full flex-col rounded-3xl border p-7 ${
        plan.popular
          ? "border-[#6d5ef7] bg-gradient-to-b from-[#1b1b3a] to-[#16181f] shadow-[0_20px_70px_rgba(79,124,255,.22)] ring-1 ring-[#4f7cff]/40"
          : "border-white/10 bg-[#16181f]"
      }`}
    >
      {plan.popular && (
        <span className="absolute -top-3 left-6 rounded-full bg-gradient-to-r from-[#4f7cff] to-[#6d5ef7] px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-white">
          Most popular
        </span>
      )}

      <p className="text-sm font-semibold text-cyan-200">{plan.name}</p>

      <div className="mt-5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
          {formatMoney(displayPrice)}
        </span>
        {plan.promoPrice && (
          <span
            aria-label={`Regular price ${formatMoney(plan.price)}, now ${formatMoney(plan.promoPrice)} first month`}
            className="text-base text-white/35 line-through sm:text-lg"
          >
            {formatMoney(plan.price)}
          </span>
        )}
        <span className="text-sm text-white/45">/month</span>
      </div>

      {plan.promoPrice ? (
        <div className="mt-3">
          <span className="rounded-full bg-cyan-300/10 px-2.5 py-1 text-xs font-semibold text-cyan-200">
            {plan.promoLabel}
          </span>
          <p className="mt-2 text-xs text-white/50">First month, then {formatMoney(plan.price)}/mo.</p>
        </div>
      ) : (
        <p className="mt-3 text-xs text-white/50">Free. No card required.</p>
      )}

      <div className="mt-7 rounded-2xl border border-white/10 bg-black/15 p-4">
        <p className="text-2xl font-semibold text-white">{plan.creditsPerDay.toLocaleString("en-IN")} credits/day</p>
        <p className="mt-1 text-sm text-cyan-200">~ {videos} videos/day</p>
        <p className="mt-2 text-xs text-white/45">Resets daily, does not roll over</p>
      </div>

      <p className="mt-5 min-h-12 text-sm leading-6 text-white/60">{plan.description}</p>
      <ul className="mt-5 flex-1 space-y-3 text-sm text-white/75">
        {plan.features.map((feature) => (
          <li key={feature} className="flex gap-2">
            <Check size={16} className="mt-0.5 shrink-0 text-cyan-200" />
            {feature}
          </li>
        ))}
      </ul>

      <Link
        href={href}
        className={`mt-7 block rounded-full px-5 py-3.5 text-center text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${
          plan.popular
            ? "bg-gradient-to-r from-[#4f7cff] to-[#6d5ef7] text-white hover:brightness-110"
            : "border border-white/15 text-white hover:bg-white/[.06]"
        }`}
      >
        {plan.id === "free" ? "Create a free account" : plan.id === "starter" ? "Start with Starter" : "Go Pro"}
      </Link>
      {plan.promoPrice && <p className="mt-3 text-center text-xs text-white/40">Promo is first-month only; standard INR price follows.</p>}
    </motion.article>
  );
}

function CreditCalculator() {
  const [videos, setVideos] = useState(6);
  const required = videos * creditsPerVideo;
  const recommended = pricingPlans.find((plan) => plan.creditsPerDay >= required) ?? pricingPlans[pricingPlans.length - 1];

  return (
    <div className="mt-12 rounded-3xl border border-white/10 bg-[#111318] p-6 sm:p-8">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.18em] text-cyan-200">Credit calculator</p>
          <h3 className="mt-3 text-2xl font-semibold text-white">How many videos/day do you process?</h3>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-3xl font-semibold text-white">{required.toLocaleString("en-IN")} credits</p>
          <p className="text-sm text-white/50">for {videos} videos/day</p>
        </div>
      </div>
      <input
        aria-label="Videos processed per day"
        type="range"
        min="1"
        max="20"
        value={videos}
        onChange={(event) => setVideos(Number(event.target.value))}
        className="mt-7 h-2 w-full cursor-pointer accent-[#4f7cff]"
      />
      <p className="mt-5 text-sm text-white/60">
        Recommended: <span className="font-semibold text-cyan-200">{recommended.name}</span> - {recommended.creditsPerDay.toLocaleString("en-IN")} credits/day
      </p>
    </div>
  );
}

function CompareTable() {
  const rows: Array<[string, (plan: PricingPlan) => string]> = [
    ["Credits/day", (plan) => plan.creditsPerDay.toLocaleString("en-IN")],
    ["Videos/day", (plan) => `~ ${videosPerDay(plan)}`],
    ["Processing speed", (plan) => plan.speed],
    ["Batch processing", (plan) => plan.batch],
    ["Retention", (plan) => plan.retention],
    ["Support", (plan) => plan.support],
  ];

  return (
    <div className="mt-16 overflow-x-auto rounded-3xl border border-white/10 bg-[#16181f]">
      <table className="w-full min-w-[720px] text-left text-sm">
        <caption className="sr-only">ClearFrame plan comparison</caption>
        <thead>
          <tr className="border-b border-white/10">
            <th className="px-5 py-4 text-xs uppercase tracking-wider text-white/45">Compare plans</th>
            {pricingPlans.map((plan) => (
              <th key={plan.id} className="px-5 py-4 font-semibold text-white">{plan.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label} className="border-b border-white/[.07] last:border-0">
              <th className="px-5 py-4 font-medium text-white/60">{label}</th>
              {pricingPlans.map((plan) => (
                <td key={plan.id} className="px-5 py-4 text-white/80">{value(plan) || <Minus size={15} className="text-white/30" />}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const faqs: Array<[string, string]> = [
  ["What is a credit?", "A credit is the unit ClearFrame uses for processing. 100 credits equals one video."],
  ["Do credits roll over?", creditPolicy.resetCopy],
  ["What happens when I run out of daily credits?", "You can wait for the next daily reset or choose a plan with a larger allowance."],
  ["Can I change plans?", "Yes. Plan changes will be available through your account as billing is introduced."],
  ["Is the offer price recurring?", "No. Promo pricing applies to the first month only, then the standard monthly price applies."],
];

function PricingFAQ() {
  const [open, setOpen] = useState<number | null>(0);
  const reduce = useReducedMotion();

  return (
    <div className="mx-auto mt-16 max-w-3xl">
      <h3 className="text-3xl font-semibold text-white">Pricing questions, answered.</h3>
      <div className="mt-8 divide-y divide-white/10 border-y border-white/10">
        {faqs.map(([question, answer], index) => {
          const isOpen = open === index;
          const panelId = `pricing-faq-panel-${index}`;
          const buttonId = `pricing-faq-button-${index}`;

          return (
            <div key={question}>
              <button
                id={buttonId}
                type="button"
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => setOpen(isOpen ? null : index)}
                className="flex min-h-16 w-full items-center justify-between gap-4 text-left font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
              >
                <span>{question}</span>
                <motion.span
                  aria-hidden="true"
                  animate={{ rotate: isOpen ? 45 : 0 }}
                  transition={{ duration: reduce ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
                  className="text-xl leading-none text-cyan-200"
                >
                  +
                </motion.span>
              </button>
              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    id={panelId}
                    role="region"
                    aria-labelledby={buttonId}
                    initial={reduce ? false : { height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
                    transition={{ duration: reduce ? 0 : 0.3, ease: [0.22, 1, 0.36, 1] }}
                    className="overflow-hidden"
                  >
                    <p className="pb-6 pr-8 leading-7 text-white/60">{answer}</p>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Pricing({ compact = false }: { compact?: boolean }) {
  return (
    <section id="pricing" className="scroll-mt-24 bg-[#0a0b0f] py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[.18em] text-cyan-200">Pricing</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-tight text-white sm:text-5xl">Simple, credit-based pricing.</h2>
          <p className="mt-5 leading-7 text-white/60">Compare daily processing capacity with clear credit allowances and plan features.</p>
        </div>
        {!compact && <CreditsInfo />}
        <div className="mt-12 grid gap-5 lg:grid-cols-3">
          {pricingPlans.map((plan, index) => <PricingCard key={plan.id} plan={plan} index={index} />)}
        </div>
        {!compact && (
          <>
            <CreditCalculator />
            <CompareTable />
            <PricingFAQ />

          </>
        )}
      </div>
    </section>
  );
}