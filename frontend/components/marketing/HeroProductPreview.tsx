"use client";

import Image from "next/image";
import { useState } from "react";
import { useReducedMotion } from "framer-motion";
import { Check, Play } from "lucide-react";

/**
 * A realistic editor-style product preview: the two real demo images in a
 * draggable before/after split with a mask box and a workflow chip. Uses
 * next/image so the ~2MB PNGs are served responsively with a fast LCP.
 */
export function HeroProductPreview() {
  const [split, setSplit] = useState(52);
  const reduce = useReducedMotion();

  return (
    <div className="relative mx-auto w-full max-w-2xl">
      <div className="overflow-hidden rounded-[1.75rem] border border-white/10 bg-[#10121f] p-3 shadow-[0_32px_100px_rgba(0,0,0,.45)]">
        <div className="overflow-hidden rounded-[1.2rem] border border-white/5">
          <div className="flex items-center justify-between border-b border-white/10 bg-[#0c0e1a] px-5 py-3 text-xs">
            <div className="flex items-center gap-2">
              <span className="flex gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
                <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
                <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
              </span>
              <span className="ml-1 font-medium text-white/80">Mask workspace</span>
            </div>
            <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2.5 py-1 font-medium text-cyan-200">
              Step 3 · Mask
            </span>
          </div>

          <div className="relative aspect-[16/10] select-none overflow-hidden bg-[#0d1226]">
            <Image
              src="/demo/owned-after-optimized.webp"
              alt="Cleaned result on sample footage"
              fill
              unoptimized
              priority
              sizes="(max-width: 1024px) 100vw, 640px"
              className="object-cover"
            />
            <div
              className="absolute inset-0"
              style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
            >
              <Image
                src="/demo/owned-before-optimized.webp"
                alt="Sample footage before cleanup, showing an overlay"
                fill
                unoptimized
                sizes="(max-width: 1024px) 100vw, 640px"
                className="object-cover"
              />
              <div className="absolute left-4 top-4 rounded-full bg-[#07080f]/80 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-white/80">
                Original
              </div>
              <div className="absolute right-[20%] top-[20%] grid h-[34%] w-[27%] place-items-center border-2 border-dashed border-cyan-300 bg-cyan-300/10">
                <span className="rounded bg-[#07080f]/80 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-200">Overlay</span>
                {!reduce && <span className="scan-line absolute inset-x-0 h-px bg-cyan-200 shadow-[0_0_18px_3px_rgba(34,211,238,.85)]" />}
              </div>
            </div>
            <div className="absolute right-4 top-4 rounded-full bg-[#07080f]/80 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-cyan-200">
              Cleaned
            </div>

            <div className="absolute inset-y-0 w-px bg-white shadow-[0_0_0_1px_rgba(10,11,15,.6)]" style={{ left: `${split}%` }}>
              <span className="absolute -left-4 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full border border-white/20 bg-[#0c0e1a] text-cyan-200 shadow-lg">
                <span className="h-3 w-px bg-current" />
              </span>
            </div>

            <input
              aria-label="Compare original and cleaned footage. Use arrow keys to move the divider."
              type="range"
              min={10}
              max={90}
              value={split}
              onChange={(e) => setSplit(Number(e.target.value))}
              className="absolute inset-0 z-10 h-full w-full cursor-ew-resize opacity-0"
            />
          </div>

          <div className="flex items-center gap-3 bg-[#0c0e1a] px-5 py-4">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-white text-[#07080f]">
              <Play size={15} fill="currentColor" />
            </span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
              <div className="h-full w-1/2 rounded-full bg-gradient-to-r from-[#4f7cff] to-[#22d3ee]" />
            </div>
            <span className="font-mono text-xs text-white/50">00:42 / 01:08</span>
          </div>
        </div>
      </div>

      <div className="absolute -bottom-5 -left-3 hidden items-start gap-2 rounded-2xl border border-white/10 bg-white/[.06] px-4 py-3 text-sm text-white shadow-xl backdrop-blur-xl sm:flex">
        <Check className="mt-0.5 h-4 w-4 shrink-0 text-cyan-200" />
        <span>
          <span className="block font-medium">Manual control when you need it</span>
          <span className="mt-0.5 block text-xs text-white/55">Fine-tune every mask, frame by frame.</span>
        </span>
      </div>
    </div>
  );
}
