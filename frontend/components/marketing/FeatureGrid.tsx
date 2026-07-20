"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";

import { features } from "./content";

const featureAccents = [
  "from-[#4f7cff]/28 to-[#4f7cff]/10 text-[#9db9ff]",
  "from-[#22d3ee]/25 to-[#22d3ee]/10 text-[#7de6f7]",
  "from-[#a78bfa]/28 to-[#a78bfa]/10 text-[#c4b0ff]",
  "from-[#34d399]/25 to-[#34d399]/10 text-[#86e8c3]",
  "from-[#fbbf24]/25 to-[#fbbf24]/10 text-[#fcd77f]",
  "from-[#f472b6]/25 to-[#f472b6]/10 text-[#f9a8d1]",
];

export function FeatureGrid() {
  const reduce = useReducedMotion();

  return (
    <section id="features" className="relative scroll-mt-24 overflow-hidden bg-[#0c0e1a] py-24 sm:py-28">
      <div className="pointer-events-none absolute right-[-8%] top-10 h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(34,211,238,.08),transparent_70%)]" />
      <div className="relative mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <div className="max-w-2xl">
          <p className="bg-gradient-to-r from-[#7de6f7] to-[#9db9ff] bg-clip-text text-xs font-semibold uppercase tracking-[.18em] text-transparent">Features</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-.03em] text-white sm:text-5xl">Everything you need to review every frame.</h2>
        </div>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f, i) => {
            const Icon = f.icon;
            const inner = (
              <>
                <div className="flex items-center justify-between">
                  <span className={`grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br ${featureAccents[i % featureAccents.length]}`}>
                    <Icon className="h-5 w-5" />
                  </span>
                  {f.href && <ArrowUpRight className="h-4 w-4 text-white/25 transition group-hover:text-cyan-200" />}
                </div>
                <h3 className="mt-5 font-semibold text-white">{f.title}</h3>
                <p className="mt-2 text-sm leading-6 text-white/55">{f.copy}</p>
              </>
            );
            return (
              <motion.div
                key={f.title}
                initial={reduce ? false : { opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.4, delay: reduce ? 0 : (i % 3) * 0.06 }}
              >
                {f.href ? (
                  <Link href={f.href} className="group block h-full rounded-2xl border border-white/[.08] bg-gradient-to-b from-white/[.05] to-white/[.02] p-6 transition hover:-translate-y-0.5 hover:border-[#4f7cff]/50 hover:from-white/[.07] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">
                    {inner}
                  </Link>
                ) : (
                  <div className="group h-full rounded-2xl border border-white/[.08] bg-gradient-to-b from-white/[.05] to-white/[.02] p-6 transition hover:-translate-y-0.5 hover:border-white/[.16]">{inner}</div>
                )}
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
