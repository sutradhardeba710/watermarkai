"use client";

import { useRef, useState } from "react";
import { Film } from "lucide-react";

import type { useMaskWorkspace } from "@/features/mask/useMaskWorkspace";

type Ws = ReturnType<typeof useMaskWorkspace>;

function fmt(t: number) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

/**
 * Timeline. For the single-region MVP the mask applies to the entire video, so
 * the active-range indicator spans the full track and the scope is labelled
 * clearly. Frame-level data stays hidden unless expanded.
 */
export function EditingTimeline({ ws, hasMask }: { ws: Ws; hasMask: boolean }) {
  const { currentTime, duration, seek } = ws;
  const [hoverPct, setHoverPct] = useState<number | null>(null);
  const trackRef = useRef<HTMLDivElement | null>(null);

  const playheadPct = duration ? Math.min(100, (currentTime / duration) * 100) : 0;

  const onHover = (e: React.MouseEvent) => {
    const el = trackRef.current;
    if (!el || !duration) return;
    const r = el.getBoundingClientRect();
    setHoverPct(Math.max(0, Math.min(100, ((e.clientX - r.left) / r.width) * 100)));
  };

  return (
    <div className="rounded-2xl border border-white/10 bg-[#10121f] p-3 sm:p-4">
      <div className="mb-3 flex flex-col items-start gap-2 text-sm sm:flex-row sm:items-center sm:justify-between">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-cyan-300/20 bg-cyan-300/[.06] px-2.5 py-1 font-medium text-cyan-100/90">
          <Film className="h-3 w-3" /> Mask applies to the entire video
        </span>
        <span className="font-mono tabular-nums text-white/50">{fmt(currentTime)} / {fmt(duration)}</span>
      </div>

      <div
        ref={trackRef}
        className="relative"
        onMouseMove={onHover}
        onMouseLeave={() => setHoverPct(null)}
      >
        {/* Mask-active range (full width for entire-video scope) */}
        {hasMask && (
          <div className="pointer-events-none absolute inset-x-0 top-1/2 z-0 h-2 -translate-y-1/2 rounded-full border border-cyan-300/25 bg-cyan-300/10" />
        )}

        <input
          aria-label="Video playhead"
          type="range"
          min={0}
          max={duration || 0}
          step={0.01}
          value={currentTime}
          onChange={(e) => seek(parseFloat(e.target.value))}
          className="editor-range relative z-10 h-11 w-full"
          style={{
            background: `linear-gradient(to right, #4f7cff 0%, #22d3ee ${playheadPct}%, rgba(255,255,255,.1) ${playheadPct}%, rgba(255,255,255,.1) 100%)`,
          }}
        />

        {hoverPct != null && duration > 0 && (
          <div
            className="pointer-events-none absolute -top-7 z-20 -translate-x-1/2 rounded-md border border-white/10 bg-[#171a2b] px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-white/80 shadow"
            style={{ left: `${hoverPct}%` }}
          >
            {fmt((hoverPct / 100) * duration)}
          </div>
        )}
      </div>
    </div>
  );
}
