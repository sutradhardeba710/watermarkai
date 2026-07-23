"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { useMarketingAuth } from "./useMarketingAuth";

export function FinalCTA() {
  const { isAuthed } = useMarketingAuth();
  const primaryHref = isAuthed ? "/dashboard" : "/signup";
  const primaryLabel = isAuthed ? "Open dashboard" : "Remove a watermark";

  return (
    <section className="bg-[#07080f] pb-24 pt-4 sm:pb-28">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <div className="relative overflow-hidden rounded-[2rem] border border-[#6d5ef7]/25 bg-gradient-to-br from-[#1a2046] via-[#10121f] to-[#2b1b56] px-7 py-14 shadow-[0_30px_120px_rgba(109,94,247,.18)] sm:px-14">
          <div className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-[#4f7cff]/25 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-28 right-1/4 h-72 w-72 rounded-full bg-[#a855f7]/15 blur-3xl" />
          <div className="pointer-events-none absolute -left-20 bottom-0 h-64 w-64 rounded-full bg-[#22d3ee]/10 blur-3xl" />
          <div className="relative max-w-2xl">
            <p className="bg-gradient-to-r from-[#9db9ff] to-[#c4b0ff] bg-clip-text text-xs font-semibold uppercase tracking-[.18em] text-transparent">Get started</p>
            <h2 className="mt-4 text-4xl font-semibold tracking-[-.03em] text-white sm:text-5xl">
              Start with the footage you are allowed to edit.
            </h2>
            <p className="mt-5 max-w-xl leading-7 text-white/65">
              Upload a short video, review the detected area, and generate a preview before committing to the full render.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                href={primaryHref}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-6 py-3.5 font-semibold text-white shadow-[0_12px_40px_rgba(109,94,247,.45)] transition hover:brightness-110 hover:shadow-[0_14px_48px_rgba(109,94,247,.6)] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
              >
                {primaryLabel} <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/pricing"
                className="inline-flex items-center justify-center rounded-full border border-white/15 px-6 py-3.5 font-semibold text-white transition hover:bg-white/[.08] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
              >
                View pricing
              </Link>
            </div>
            {!isAuthed && <p className="mt-4 text-xs text-white/50">No credit card required for the Free plan.</p>}
          </div>
        </div>
      </div>
    </section>
  );
}
