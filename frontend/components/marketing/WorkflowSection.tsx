import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { workflowSteps } from "./content";

/** Per-step accent hues so the sequence reads as a journey, not six clones. */
const stepAccents = [
  { chip: "from-[#4f7cff]/30 to-[#4f7cff]/10 text-[#9db9ff]", hover: "hover:border-[#4f7cff]/40" },
  { chip: "from-[#22d3ee]/25 to-[#22d3ee]/10 text-[#7de6f7]", hover: "hover:border-[#22d3ee]/40" },
  { chip: "from-[#a78bfa]/28 to-[#a78bfa]/10 text-[#c4b0ff]", hover: "hover:border-[#a78bfa]/40" },
  { chip: "from-[#f472b6]/25 to-[#f472b6]/10 text-[#f9a8d1]", hover: "hover:border-[#f472b6]/40" },
  { chip: "from-[#fbbf24]/25 to-[#fbbf24]/10 text-[#fcd77f]", hover: "hover:border-[#fbbf24]/40" },
  { chip: "from-[#34d399]/25 to-[#34d399]/10 text-[#86e8c3]", hover: "hover:border-[#34d399]/40" },
];

export function WorkflowSection() {
  return (
    <section id="workflow" className="relative scroll-mt-24 overflow-hidden bg-[#0c0e1a] py-24 sm:py-28">
      <div className="pointer-events-none absolute left-1/2 top-0 h-64 w-[50rem] -translate-x-1/2 rounded-full bg-[radial-gradient(ellipse,rgba(167,139,250,.09),transparent_70%)]" />
      <div className="relative mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <div className="max-w-2xl">
          <p className="bg-gradient-to-r from-[#7de6f7] to-[#9db9ff] bg-clip-text text-xs font-semibold uppercase tracking-[.18em] text-transparent">How it works</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-.03em] text-white sm:text-5xl">How to remove a watermark from a video online.</h2>
          <p className="mt-4 text-lg leading-8 text-white/60">Upload, detect, refine, preview, and export while you stay in control at every stage.</p>
        </div>

        <ol className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {workflowSteps.map((step, i) => {
            const Icon = step.icon;
            const isLast = i === workflowSteps.length - 1;
            return (
              <li
                key={step.n}
                className={`relative flex flex-col rounded-2xl border border-white/[.08] bg-gradient-to-b from-white/[.05] to-white/[.02] p-6 transition ${stepAccents[i % stepAccents.length].hover}`}
              >
                <div className="flex items-center justify-between">
                  <span className={`grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br ${stepAccents[i % stepAccents.length].chip}`}>
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="font-mono text-sm font-semibold tracking-widest text-white/25">{step.n}</span>
                </div>
                <h3 className="mt-5 text-lg font-semibold text-white">{step.title}</h3>
                <p className="mt-2 text-sm leading-6 text-white/55">{step.copy}</p>
                {!isLast && (
                  <ArrowRight className="absolute -right-2 top-1/2 hidden h-4 w-4 -translate-y-1/2 text-white/20 lg:block" aria-hidden="true" />
                )}
              </li>
            );
          })}
        </ol>

        <div className="mt-12">
          <Link href="/signup" className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[.03] px-6 py-3.5 font-semibold text-white transition hover:border-white/30 hover:bg-white/[.07]">
            Create your first project <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </section>
  );
}
