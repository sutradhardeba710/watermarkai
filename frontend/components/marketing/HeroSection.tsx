"use client";

import Link from "next/link";
import { motion, useReducedMotion, type Variants } from "framer-motion";
import { ArrowRight, Play } from "lucide-react";

import { HeroProductPreview } from "./HeroProductPreview";
import { TrustIndicators } from "./TrustIndicators";
import { useMarketingAuth } from "./useMarketingAuth";

const ease = [0.22, 1, 0.36, 1] as const;
const reveal: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease } },
};

export function HeroSection() {
  const reduce = useReducedMotion();
  const { isAuthed } = useMarketingAuth();

  const primaryHref = isAuthed ? "/dashboard" : "/signup";
  const primaryLabel = isAuthed ? "Open dashboard" : "Remove a watermark";

  return (
    <section id="top" className="relative isolate mx-auto max-w-7xl px-4 pb-16 pt-24 sm:px-8 sm:pb-20 sm:pt-32 lg:px-10 lg:pb-28">
      {/* Layered ambient mesh: indigo core, violet + cyan side glows, faint grid masked toward the fold */}
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[44rem] bg-[radial-gradient(ellipse_at_top,rgba(79,124,255,.18),transparent_60%)]" />
      <div className="pointer-events-none absolute -top-24 right-[-10%] -z-10 h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(168,85,247,.14),transparent_65%)]" />
      <div className="pointer-events-none absolute left-[-12%] top-64 -z-10 h-[26rem] w-[26rem] rounded-full bg-[radial-gradient(circle,rgba(34,211,238,.10),transparent_65%)]" />
      <div className="pointer-events-none absolute inset-0 -z-10 opacity-25 [background-image:linear-gradient(rgba(255,255,255,.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.03)_1px,transparent_1px)] [background-size:52px_52px] [mask-image:linear-gradient(to_bottom,black,transparent_80%)]" />

      <div className="grid items-center gap-14 lg:grid-cols-[.92fr_1.08fr]">
        <motion.div variants={reveal} initial={reduce ? false : "hidden"} animate="visible">
          <p className="inline-flex items-center gap-2 rounded-full border border-[#4f7cff]/35 bg-gradient-to-r from-[#4f7cff]/15 to-[#a855f7]/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[.16em] text-[#b7c7ff]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#22d3ee] shadow-[0_0_8px_rgba(34,211,238,.9)]" />
            Online AI video watermark remover
          </p>
          <h1 className="mt-6 max-w-2xl text-4xl font-semibold leading-[1.05] tracking-[-.035em] min-[390px]:text-[2.65rem] sm:text-6xl lg:text-[4.2rem]">
            Remove video watermarks.{" "}
            <span className="bg-gradient-to-r from-[#6d9bff] via-[#a78bfa] to-[#22d3ee] bg-clip-text text-transparent">Keep frame-level control.</span>
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 sm:mt-6 sm:text-lg sm:leading-8 text-[#9ca3af]">
            Use AI to detect and remove your old logos, date stamps, hardcoded subtitles, and unwanted overlays from MP4, MOV, or WebM videos. Refine the mask, preview the result, and export only when you are satisfied.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href={primaryHref}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-6 py-3.5 text-center font-semibold text-white shadow-[0_12px_40px_rgba(109,94,247,.45)] transition hover:brightness-110 hover:shadow-[0_14px_48px_rgba(109,94,247,.6)] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07080f]"
            >
              {primaryLabel} <ArrowRight className="h-4 w-4" />
            </Link>
            <a
              href="#proof"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 bg-white/[.03] px-6 py-3.5 text-center font-semibold text-white transition hover:border-white/30 hover:bg-white/[.07] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
            >
              <Play className="h-4 w-4" /> See how it works
            </a>
          </div>

          <div className="mt-7">
            <TrustIndicators />
          </div>
        </motion.div>

        <motion.div variants={reveal} initial={reduce ? false : "hidden"} animate="visible" transition={{ delay: reduce ? 0 : 0.12 }}>
          <HeroProductPreview />
        </motion.div>
      </div>
    </section>
  );
}
