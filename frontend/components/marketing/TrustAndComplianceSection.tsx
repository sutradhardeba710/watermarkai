"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { trustPrinciples } from "./content";

const retention = [
  ["Source video", "Kept only for the active workflow, then removed on schedule."],
  ["Preview clips", "Short-lived; cleared automatically after review."],
  ["Cleaned output", "Available to download for a limited retention window."],
];

export function TrustAndComplianceSection() {
  return (
    <section id="compliance" className="scroll-mt-24 bg-[#0c0e1a] py-24 sm:py-28">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <div className="grid gap-12 lg:grid-cols-[.85fr_1.15fr]">
          <div>
            <p className="bg-gradient-to-r from-emerald-300 to-cyan-300 bg-clip-text text-xs font-semibold uppercase tracking-[.18em] text-transparent">Trust &amp; privacy</p>
            <h2 className="mt-4 text-4xl font-semibold tracking-[-.03em] text-white sm:text-5xl">Your footage stays under your control.</h2>
            <p className="mt-5 max-w-md leading-7 text-white/60">
              ClearFrame is designed for footage you own, license, or are authorized to edit — with clear guardrails, private storage, and files that don&apos;t linger.
            </p>

            <div className="mt-7 rounded-2xl border border-white/10 bg-black/20 p-5">
              <p className="text-sm font-semibold text-white/80">File retention at a glance</p>
              <ul className="mt-3 space-y-2.5">
                {retention.map(([label, copy]) => (
                  <li key={label} className="flex gap-3 text-sm">
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-300/70" />
                    <span><span className="font-medium text-white/75">{label}:</span> <span className="text-white/50">{copy}</span></span>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-xs leading-6 text-white/45">
                Your videos are never used to train models without your explicit opt-in, and you can delete a project&apos;s files at any time.
              </p>
            </div>

            <div className="mt-7 flex flex-wrap gap-3">
              <Link href="/authorized-use" className="inline-flex items-center gap-2 rounded-full bg-white/[.06] px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/[.1]">
                Read our authorized-use policy <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-white/45">
              <Link href="/acceptable-use" className="hover:text-white">Acceptable Use Policy</Link>
              <Link href="/privacy" className="hover:text-white">Privacy Policy</Link>
              <Link href="/terms" className="hover:text-white">Terms</Link>
              <Link href="/authorized-use" className="hover:text-white">Data Retention</Link>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {trustPrinciples.map((p) => {
              const Icon = p.icon;
              return (
                <div key={p.title} className="rounded-2xl border border-white/[.08] bg-gradient-to-b from-white/[.05] to-white/[.02] p-6 transition hover:border-emerald-300/30">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-300/10 text-emerald-200">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-5 font-semibold text-white">{p.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-white/55">{p.copy}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
