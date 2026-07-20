"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowLeft,
  BadgeDollarSign,
  ChevronDown,
  FileVideo,
  LifeBuoy,
  Mail,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Wifi,
} from "lucide-react";
import { UserMenu } from "@/features/account/UserMenu";
import { useAuthStore } from "@/features/auth/authStore";
import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { seoPageByPath } from "@/components/seoPages";

// Quick links only point at routes that actually exist (SEO catch-all pages
// and real app pages) — no dead destinations.
const QUICK_LINKS = [
  { label: "Billing & subscription", desc: "Plan, credits, and cancellation", href: "/billing", icon: BadgeDollarSign },
  { label: "Supported formats", desc: "MP4 · MOV · WebM and upload rules", href: "/supported-formats", icon: FileVideo },
  { label: "Authorized use", desc: "What footage you can process", href: "/authorized-use", icon: ShieldCheck },
  { label: "Service status", desc: "Current system health", href: "/status", icon: Wifi },
];

const LEGAL_LINKS = [
  { label: "Terms of Service", href: "/terms" },
  { label: "Privacy Policy", href: "/privacy" },
  { label: "Acceptable Use", href: "/acceptable-use" },
  { label: "Security", href: "/security" },
];

function FaqItem({ q, a, open, onToggle }: { q: string; a: string; open: boolean; onToggle: () => void }) {
  return (
    <div className="rounded-2xl border border-white/[.08] bg-white/[.03] transition hover:border-white/15">
      <button onClick={onToggle} aria-expanded={open} className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left">
        <span className="text-sm font-medium text-white">{q}</span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-white/40 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <p className="px-5 pb-5 text-sm leading-6 text-white/55">{a}</p>}
    </div>
  );
}

export default function SupportPage() {
  useHydrateAuth();
  const user = useAuthStore((s) => s.user);
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  // Reuse the canonical FAQ content instead of duplicating it here.
  const faq = seoPageByPath.get("faq")?.sections ?? [];

  return (
    <main className="min-h-dvh bg-[#07080f] text-[#f5f6fa]">
      <div className="pointer-events-none fixed left-1/2 top-0 z-0 h-96 w-[60rem] -translate-x-1/2 bg-[radial-gradient(ellipse_at_top,rgba(79,124,255,.08),transparent_65%)]" />

      <header className="sticky top-0 z-20 border-b border-white/[.07] bg-[#07080f]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-20 max-w-4xl items-center justify-between px-5 sm:px-8">
          <div className="flex items-center gap-4">
            <Link
              href={user ? "/dashboard" : "/"}
              className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 text-white/55 transition hover:text-white"
              aria-label={user ? "Back to dashboard" : "Back to home"}
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <Link href="/" className="flex items-center gap-2.5 text-lg font-semibold tracking-tight">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] text-white shadow-[0_0_22px_rgba(79,124,255,.35)]">
                <Sparkles className="h-5 w-5" />
              </span>
              ClearFrame
            </Link>
          </div>
          {user && <UserMenu />}
        </div>
      </header>

      <div className="relative mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-14">
        <div className="text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-[#4f7cff]/20 to-[#6d5ef7]/20 text-[#9eb4ff]">
            <LifeBuoy className="h-7 w-7" />
          </span>
          <h1 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">How can we help?</h1>
          <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-white/55">
            Answers to common questions, guides for your account, and ways to reach the ClearFrame team.
          </p>
        </div>

        <section aria-label="Quick help topics" className="mt-10 grid gap-3 sm:grid-cols-2">
          {QUICK_LINKS.map(({ label, desc, href, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="group flex items-start gap-4 rounded-2xl border border-white/[.08] bg-gradient-to-b from-white/[.05] to-white/[.02] p-5 transition hover:-translate-y-0.5 hover:border-[#4f7cff]/35 hover:shadow-[0_16px_50px_rgba(79,124,255,.12)]"
            >
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#4f7cff]/15 text-[#9db9ff]">
                <Icon className="h-5 w-5" />
              </span>
              <span>
                <span className="block text-sm font-semibold text-white">{label}</span>
                <span className="mt-1 block text-xs text-white/45">{desc}</span>
              </span>
            </Link>
          ))}
        </section>

        {faq.length > 0 && (
          <section aria-label="Frequently asked questions" className="mt-12">
            <h2 className="text-lg font-semibold">Frequently asked questions</h2>
            <div className="mt-4 space-y-3">
              {faq.map((item, i) => (
                <FaqItem
                  key={item.title}
                  q={item.title}
                  a={item.body}
                  open={openFaq === i}
                  onToggle={() => setOpenFaq(openFaq === i ? null : i)}
                />
              ))}
            </div>
          </section>
        )}

        <section aria-label="Contact" className="mt-12 rounded-3xl border border-[#4f7cff]/25 bg-gradient-to-br from-[#1a2046] via-[#141833] to-[#0e1020] p-6 sm:p-8">
          <div className="flex flex-col items-start justify-between gap-5 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-lg font-semibold">Still need help?</h2>
              <p className="mt-1.5 max-w-md text-sm leading-6 text-white/55">
                Reach the team for product support, security reports, or business inquiries.
              </p>
            </div>
            <Link
              href="/contact"
              className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-110"
            >
              <Mail className="h-4 w-4" />
              Contact us
            </Link>
          </div>
        </section>

        <nav aria-label="Legal" className="mt-10 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-white/40">
          <ScrollText className="h-3.5 w-3.5" />
          {LEGAL_LINKS.map(({ label, href }) => (
            <Link key={href} href={href} className="hover:text-white">
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </main>
  );
}
