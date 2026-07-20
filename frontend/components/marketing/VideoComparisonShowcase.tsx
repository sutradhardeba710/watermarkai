"use client";

import Link from "next/link";
import Image from "next/image";
import { useState } from "react";
import { useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";

import { examples } from "./content";
import { cn } from "@/lib/utils";

/**
 * The strongest visual proof on the page: a large, accessible before/after
 * comparison of the two real demo images, plus honest example categories.
 * Because only two sample images exist, examples share them and are labelled as
 * illustrative — no fabricated per-clip durations or metrics.
 */
export function VideoComparisonShowcase() {
  const [split, setSplit] = useState(50);
  const [activeId, setActiveId] = useState(examples[0].id);
  const [imgError, setImgError] = useState(false);
  const reduce = useReducedMotion();
  const active = examples.find((e) => e.id === activeId) ?? examples[0];

  return (
    <section id="proof" className="scroll-mt-24 relative overflow-hidden bg-[#07080f] py-24 sm:py-28">
      <div className="pointer-events-none absolute left-1/2 top-16 -z-0 h-80 w-[42rem] -translate-x-1/2 rounded-full bg-[#4f7cff]/10 blur-3xl" />
      <div className="pointer-events-none absolute right-[8%] top-40 -z-0 h-56 w-56 rounded-full bg-[#a855f7]/10 blur-3xl" />
      <div className="relative mx-auto max-w-6xl px-5 sm:px-8 lg:px-10">
        <div className="mx-auto max-w-2xl text-center">
          <p className="bg-gradient-to-r from-[#7de6f7] to-[#9db9ff] bg-clip-text text-xs font-semibold uppercase tracking-[.18em] text-transparent">Product proof</p>
          <h2 className="mt-4 text-4xl font-semibold tracking-[-.03em] text-white sm:text-5xl">See exactly what changes.</h2>
          <p className="mt-5 leading-7 text-white/60">Compare the original footage with the cleaned result before starting a full render.</p>
        </div>

        <div className="mx-auto mt-12 max-w-4xl overflow-hidden rounded-[1.75rem] border border-white/[.1] bg-gradient-to-b from-[#151834] to-[#0e1020] p-3 shadow-[0_30px_100px_rgba(10,10,30,.6)]">
          {reduce ? (
            // Reduced-motion / no-drag fallback: static side-by-side.
            <div className="grid grid-cols-2 gap-2">
              <FallbackPane src="/demo/owned-before.png" label="Original" onError={() => setImgError(true)} error={imgError} />
              <FallbackPane src="/demo/owned-after.png" label="Cleaned" onError={() => setImgError(true)} error={imgError} />
            </div>
          ) : (
            <div className="relative aspect-[16/9] select-none overflow-hidden rounded-2xl bg-[#0d1226]">
              {imgError ? (
                <div className="grid h-full place-items-center px-6 text-center text-sm text-white/50">
                  The sample preview couldn&apos;t load. Please refresh to try again.
                </div>
              ) : (
                <>
                  <Image src="/demo/owned-after.png" alt="Cleaned sample result" fill sizes="(max-width: 896px) 100vw, 896px" className="object-cover" onError={() => setImgError(true)} />
                  <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}>
                    <Image src="/demo/owned-before.png" alt="Original sample footage with overlay" fill sizes="(max-width: 896px) 100vw, 896px" className="object-cover" />
                    <span className="absolute left-5 top-5 rounded-full bg-[#07080f]/80 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-white/80">Original</span>
                  </div>
                  <span className="absolute right-5 top-5 rounded-full bg-[#07080f]/80 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-200">Cleaned</span>
                  <div className="absolute inset-y-0 w-px bg-white shadow-[0_0_0_1px_rgba(10,11,15,.65)]" style={{ left: `${split}%` }}>
                    <span className="absolute -left-4 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full border border-white/20 bg-[#0c0e1a] text-cyan-200 shadow-lg">
                      <span className="h-3 w-px bg-current" />
                    </span>
                  </div>
                  <input
                    aria-label="Drag or use arrow keys to compare original and cleaned footage"
                    type="range"
                    min={10}
                    max={90}
                    value={split}
                    onChange={(e) => setSplit(Number(e.target.value))}
                    className="absolute inset-0 z-10 h-full w-full cursor-ew-resize opacity-0"
                  />
                </>
              )}
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 px-3 pb-1 pt-4 sm:px-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold text-white">{active.label}</p>
                <span className="rounded-full bg-cyan-300/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-200">{active.mode} mode</span>
                <span className="rounded-full border border-white/10 px-2.5 py-1 text-[10px] font-medium text-white/45">Illustrative sample</span>
              </div>
              <p className="mt-1.5 text-sm text-white/55">Removed: {active.removed}</p>
            </div>
            <p className="text-xs text-white/40">{reduce ? "Static comparison" : "Drag the handle to compare"}</p>
          </div>
        </div>

        {/* Example selector — honest categories sharing the real sample images */}
        <div className="mt-8">
          <div className="flex snap-x gap-3 overflow-x-auto pb-2 sm:grid sm:grid-cols-4 sm:overflow-visible">
            {examples.map((ex) => {
              const selected = ex.id === activeId;
              return (
                <button
                  key={ex.id}
                  type="button"
                  onClick={() => setActiveId(ex.id)}
                  aria-pressed={selected}
                  className={cn(
                    "group w-[220px] shrink-0 snap-start rounded-2xl border p-2 text-left transition sm:w-auto",
                    selected ? "border-[#4f7cff] bg-[#4f7cff]/10 shadow-[0_8px_30px_rgba(79,124,255,.25),0_0_0_1px_rgba(79,124,255,.35)]" : "border-white/[.08] bg-white/[.03] hover:-translate-y-1 hover:border-white/25",
                  )}
                >
                  <div className="relative aspect-[16/9] overflow-hidden rounded-xl">
                    <Image src="/demo/owned-after.png" alt="" fill sizes="220px" loading="lazy" className="object-cover transition duration-300 group-hover:scale-105" />
                    <span className="absolute bottom-2 right-2 rounded-full bg-[#07080f]/85 px-2 py-0.5 text-[10px] font-medium text-white/80">{ex.mode}</span>
                  </div>
                  <p className="mt-2.5 truncate text-sm font-semibold text-white">{ex.label}</p>
                  <p className="mt-0.5 line-clamp-1 text-xs text-white/45">{ex.removed}</p>
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/signup" className="rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-6 py-3.5 font-semibold text-white shadow-[0_10px_30px_rgba(79,124,255,.28)] transition hover:brightness-110">
            Try with your video
          </Link>
          <a href="#workflow" className="inline-flex items-center gap-2 rounded-full border border-white/15 px-6 py-3.5 font-semibold text-white transition hover:bg-white/[.06]">
            See the workflow <ArrowRight className="h-4 w-4" />
          </a>
        </div>
      </div>
    </section>
  );
}

function FallbackPane({ src, label, onError, error }: { src: string; label: string; onError: () => void; error: boolean }) {
  return (
    <div className="relative aspect-[16/9] overflow-hidden rounded-2xl bg-[#0d1226]">
      {error ? (
        <div className="grid h-full place-items-center text-xs text-white/45">Preview unavailable</div>
      ) : (
        <Image src={src} alt={`${label} sample`} fill sizes="(max-width: 896px) 50vw, 448px" className="object-cover" onError={onError} />
      )}
      <span className="absolute left-3 top-3 rounded-full bg-[#07080f]/80 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-white/80">{label}</span>
    </div>
  );
}
