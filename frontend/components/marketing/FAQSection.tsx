"use client";

import { useMemo, useState } from "react";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { faqItems, type FaqCategory } from "./content";
import { cn } from "@/lib/utils";

const CATEGORIES: (FaqCategory | "All")[] = ["All", "Product", "Processing", "Credits & billing", "Privacy", "Authorized use"];

export function FAQSection() {
  const [filter, setFilter] = useState<FaqCategory | "All">("All");
  const visible = useMemo(
    () => (filter === "All" ? faqItems : faqItems.filter((f) => f.category === filter)),
    [filter],
  );

  return (
    <section id="faq" className="scroll-mt-24 bg-[#07080f] py-24 sm:py-28">
      <div className="mx-auto max-w-3xl px-5 sm:px-8">
        <div className="text-center">
          <p className="bg-gradient-to-r from-[#7de6f7] to-[#9db9ff] bg-clip-text text-xs font-semibold uppercase tracking-[.18em] text-transparent">FAQ</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-.03em] text-white sm:text-5xl">Answers before you start.</h2>
        </div>

        <div className="mt-8 flex flex-wrap justify-center gap-2">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setFilter(cat)}
              aria-pressed={filter === cat}
              className={cn(
                "rounded-full border px-3.5 py-1.5 text-xs font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300",
                filter === cat ? "border-cyan-300/40 bg-cyan-300/10 text-cyan-200" : "border-white/10 text-white/55 hover:text-white",
              )}
            >
              {cat}
            </button>
          ))}
        </div>

        <Accordion type="single" collapsible defaultValue="faq-0" className="mt-8 border-t border-white/10">
          {visible.map((item, i) => (
            <AccordionItem key={item.q} value={`faq-${i}`}>
              <AccordionTrigger>{item.q}</AccordionTrigger>
              <AccordionContent>{item.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}
