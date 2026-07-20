"use client";

import { Check, X } from "lucide-react";

import { basicRemoverPoints, clearFramePoints } from "./content";

export function QualityComparison() {
  return (
    <section id="quality" className="scroll-mt-24 bg-[#07080f] py-24 sm:py-28">
      <div className="mx-auto max-w-6xl px-5 sm:px-8 lg:px-10">
        <div className="mx-auto max-w-2xl text-center">
          <p className="bg-gradient-to-r from-[#9db9ff] to-[#c4b0ff] bg-clip-text text-xs font-semibold uppercase tracking-[.18em] text-transparent">Quality &amp; control</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-.03em] text-white sm:text-5xl">Not just blur, crop, or cover.</h2>
          <p className="mt-5 leading-7 text-white/60">
            ClearFrame uses mask-based reconstruction and temporal processing to rebuild the selected area while preserving the surrounding footage.
          </p>
        </div>

        <div className="mt-12 grid gap-4 lg:grid-cols-2">
          <div className="rounded-3xl border border-rose-400/[.12] bg-gradient-to-br from-rose-500/[.05] to-white/[.02] p-7">
            <p className="text-sm font-semibold text-rose-200/70">Basic remover</p>
            <ul className="mt-5 space-y-3">
              {basicRemoverPoints.map((point) => (
                <li key={point} className="flex items-center gap-3 text-sm text-white/55">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-rose-400/10 text-rose-300/70">
                    <X className="h-3.5 w-3.5" />
                  </span>
                  {point}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-3xl border border-emerald-300/25 bg-gradient-to-br from-emerald-400/[.08] via-cyan-400/[.05] to-white/[.02] p-7 shadow-[0_18px_60px_rgba(52,211,153,.12)]">
            <p className="bg-gradient-to-r from-emerald-300 to-cyan-300 bg-clip-text text-sm font-semibold text-transparent">ClearFrame</p>
            <ul className="mt-5 space-y-3">
              {clearFramePoints.map((point) => (
                <li key={point} className="flex items-center gap-3 text-sm text-white/80">
                  <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-emerald-300/15 text-emerald-200">
                    <Check className="h-3.5 w-3.5" />
                  </span>
                  {point}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <p className="mx-auto mt-6 max-w-2xl text-center text-xs leading-6 text-white/40">
          Results depend on scene complexity, movement, mask accuracy, and source quality.
        </p>
      </div>
    </section>
  );
}
