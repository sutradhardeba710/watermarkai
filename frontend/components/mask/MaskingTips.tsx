"use client";

import { useState } from "react";
import { ChevronDown, Lightbulb } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { cn } from "@/lib/utils";

const TIPS = [
  "Select slightly beyond the visible watermark edge.",
  "Use Feather to blend hard edges.",
  "Use Brush for irregular shapes.",
  "Check several timestamps before continuing.",
  "Use AI Detect as a starting point, not a final result.",
  "Preview before running the full render.",
];

export function MaskingTips() {
  const [open, setOpen] = useState(false);
  const reduce =
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  return (
    <section className="rounded-2xl border border-white/10 bg-[#10121f]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-2xl px-4 py-3 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"
      >
        <Lightbulb className="h-4 w-4 text-amber-300/80" />
        <span className="flex-1 text-sm font-medium text-white/80">Masking tips</span>
        <ChevronDown className={cn("h-4 w-4 text-white/40 transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={reduce ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduce ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <ul className="space-y-2 px-4 pb-4 pt-0">
              {TIPS.map((tip) => (
                <li key={tip} className="flex gap-2 text-xs leading-5 text-white/55">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-cyan-300/60" />
                  {tip}
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
