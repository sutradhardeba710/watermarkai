"use client";

import Image from "next/image";
import { useMemo, useState } from "react";
import { Filter, MoveRight } from "lucide-react";
import { videoExamples, type VideoExampleMode } from "./videoExamples";

type FilterName = "All" | "Logo" | "Timestamp" | "Subtitle" | "Overlay" | "Branding" | "Presentation" | VideoExampleMode;
const filters: FilterName[] = ["All", "Logo", "Timestamp", "Subtitle", "Overlay", "Branding", "Presentation", "Fast", "Balanced", "High Quality"];

export function ExamplesGallery() {
  const [active, setActive] = useState<FilterName>("All");
  const visible = useMemo(() => active === "All" ? videoExamples : videoExamples.filter((example) => example.mode === active || example.category === active.toLowerCase()), [active]);

  return <section aria-labelledby="example-gallery-title" className="bg-[#f5f6f8] py-24 text-[#0c0e1a] sm:py-32"><div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
    <div className="flex flex-col justify-between gap-7 lg:flex-row lg:items-end"><div><p className="text-xs font-semibold uppercase tracking-[.18em] text-[#4f7cff]">Example gallery</p><h2 id="example-gallery-title" className="mt-4 max-w-3xl text-4xl font-semibold tracking-[-.04em] sm:text-5xl">Six scenes. Six distinct cleanup decisions.</h2><p className="mt-5 max-w-2xl leading-7 text-slate-600">Every pair uses the exact same generated frame. Only its fictional demonstration overlay changes.</p></div><div className="inline-flex items-center gap-2 text-sm font-medium text-slate-500"><Filter size={16} /> {visible.length} examples shown</div></div>
    <div className="mt-9 flex gap-2 overflow-x-auto pb-3" aria-label="Filter video examples">{filters.map((filter) => <button type="button" key={filter} aria-pressed={active === filter} onClick={() => setActive(filter)} className={`min-h-11 shrink-0 rounded-full border px-4 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4f7cff] ${active === filter ? "border-[#4f7cff] bg-[#4f7cff] text-white" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"}`}>{filter}</button>)}</div>
    <div className="mt-8 grid gap-5 lg:grid-cols-2">{visible.map((example) => <article key={example.id} className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_16px_44px_rgba(21,24,31,.07)]"><div className="grid grid-cols-2 gap-px bg-slate-200"><ExampleImage src={example.thumbnailOriginal} alt={example.altOriginal} label="Original" /><ExampleImage src={example.thumbnailCleaned} alt={example.altCleaned} label="Cleaned" cleaned /></div><div className="p-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-xl font-semibold tracking-[-.02em]">{example.title}</h3><p className="mt-2 max-w-lg text-sm leading-6 text-slate-600">{example.description}</p></div><span className="rounded-full bg-[#4f7cff]/10 px-3 py-1 text-xs font-semibold text-[#365fd5]">{example.mode}</span></div><dl className="mt-5 grid gap-3 border-y border-slate-100 py-4 text-sm sm:grid-cols-2"><div><dt className="text-xs text-slate-400">Mask type</dt><dd className="mt-1 font-medium">{example.maskType}</dd></div><div><dt className="text-xs text-slate-400">Media</dt><dd className="mt-1 font-medium">Generated demonstration</dd></div></dl><p className="mt-4 text-sm leading-6 text-slate-600">{example.detailedDescription}</p><p className="mt-4 inline-flex items-start gap-2 text-xs font-semibold leading-5 text-slate-500"><MoveRight size={14} className="mt-0.5 shrink-0 text-[#4f7cff]" /> {example.disclaimer}</p></div></article>)}</div>
    {visible.length === 0 && <p className="mt-8 rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-500">No examples match this filter.</p>}
  </div></section>;
}

function ExampleImage({ src, alt, label, cleaned = false }: { src: string; alt: string; label: string; cleaned?: boolean }) {
  return <div className="bg-white"><div className="relative aspect-video overflow-hidden"><Image src={src} alt={alt} fill unoptimized sizes="(max-width: 1024px) 50vw, 320px" className="object-cover" /></div><p className={`px-3 py-2 text-[10px] font-semibold uppercase tracking-wider ${cleaned ? "text-[#4f7cff]" : "text-slate-500"}`}>{label}</p></div>;
}

