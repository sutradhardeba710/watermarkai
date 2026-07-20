"use client";

import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useState } from "react";

const betaPlans = [{
  name: "Beta access",
  description: "Everything you need to try ClearFrame on authorized footage.",
  items: ["Authorized video cleanup", "AI detection and manual mask control", "Before/after preview and review", "Original audio, resolution, and frame rate preserved"],
}];

const faqs = [
  ["Is this legal?", "Yes, when you own the video or are licensed to edit it. You confirm this before processing. Removing third-party ownership marks, paid stock watermarks, or DRM-protected content is prohibited."],
  ["What video formats can I use?", "The beta supports MP4, MOV, and WebM uploads, subject to the product validation limits."],
  ["Do you keep my videos?", "Files are retained only for the product workflow and are governed by the configured retention policy. Secure, controlled downloads are used for outputs."],
  ["How long does processing take?", "It depends on the clip length, resolution, selected mask, and queue load. You can review a short preview before approving a full render."],
  ["What quality do I get back?", "The workflow is designed to preserve original audio, resolution, frame rate, aspect ratio, and duration where technically possible."],
];

export default function MarketingSections() {
  const [open, setOpen] = useState<number | null>(0);
  const reduceMotion = useReducedMotion();
  return <>
    <section id="compliance" className="scroll-mt-24 bg-[#0c0e1a] py-24 sm:py-32"><div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10"><div className="grid gap-12 lg:grid-cols-2"><div><p className="text-xs font-semibold uppercase tracking-[.18em] text-[#b7c7ff]">Built for legitimate work</p><h2 className="mt-4 text-4xl font-semibold tracking-[-.04em] text-white sm:text-5xl">Compliance built into the workflow, not buried in fine print.</h2><p className="mt-5 max-w-xl leading-7 text-white/60">ClearFrame makes the authorization boundary visible, rather than burying it in fine print.</p><div className="mt-8 grid gap-3 sm:grid-cols-2">{["Ownership confirmation before processing", "Controlled output downloads", "Configurable retention policy", "No DRM removal"].map((item) => <div key={item} className="rounded-2xl border border-white/10 bg-white/[.03] p-4 text-sm font-medium text-white/80">{item}</div>)}</div></div><div className="rounded-3xl border border-cyan-300/20 bg-[radial-gradient(circle_at_top,rgba(34,211,238,.15),transparent_56%)] p-7"><p className="text-sm font-semibold text-cyan-200">Try the interactive comparison</p><h3 className="mt-3 text-2xl font-semibold text-white">See the review experience before you create an account.</h3><p className="mt-4 leading-7 text-white/60">The hero comparison is a live sample. Drag the handle to inspect an overlay region and its cleaned result.</p><a href="#top" className="mt-7 inline-block rounded-full border border-white/15 px-5 py-3 text-sm font-semibold text-white hover:bg-white/10">Back to the demo</a></div></div></div></section>
    <section id="faq" className="scroll-mt-24 bg-[#f7f8fb] py-24 text-[#0c0e1a] sm:py-32"><div className="mx-auto max-w-3xl px-5 sm:px-8"><p className="text-xs font-semibold uppercase tracking-[.18em] text-[#4f7cff]">Questions, answered</p><h2 className="mt-4 text-4xl font-semibold tracking-[-.04em] sm:text-5xl">Everything you need to know before you start.</h2><div className="mt-12 divide-y divide-slate-200 border-y border-slate-200">{faqs.map(([question, answer], index) => { const expanded = open === index; return <div key={question}><button type="button" onClick={() => setOpen(expanded ? null : index)} aria-expanded={expanded} aria-controls={`faq-answer-${index}`} id={`faq-button-${index}`} className="flex min-h-16 w-full cursor-pointer items-center justify-between gap-5 py-5 text-left font-semibold outline-none focus-visible:ring-2 focus-visible:ring-[#4f7cff] focus-visible:ring-offset-4"><span>{question}</span><motion.span aria-hidden="true" animate={{ rotate: expanded ? 45 : 0 }} transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }} className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-xl text-[#4f7cff]">+</motion.span></button><AnimatePresence initial={false}>{expanded && <motion.div id={`faq-answer-${index}`} role="region" aria-labelledby={`faq-button-${index}`} initial={{ height: 0, opacity: 0, y: -4 }} animate={{ height: "auto", opacity: 1, y: 0 }} exit={{ height: 0, opacity: 0, y: -4 }} transition={{ duration: reduceMotion ? 0 : 0.26, ease: [0.22, 1, 0.36, 1] }} className="overflow-hidden"><p className="pb-6 pr-12 leading-7 text-slate-600">{answer}</p></motion.div>}</AnimatePresence></div>; })}</div></div></section>
  </>;
}

