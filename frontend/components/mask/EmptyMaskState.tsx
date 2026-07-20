"use client";

import { ScanSearch, Target } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Shown in the inspector while no mask exists. Guides the user toward AI Detect
 * (recommended) or a manual tool, and previews the three-step flow. Collapses
 * automatically once a mask is created (rendered conditionally by the parent).
 */
export function EmptyMaskState({ onAiDetect, disabled }: { onAiDetect: () => void; disabled?: boolean }) {
  return (
    <section className="rounded-2xl border border-white/10 bg-gradient-to-b from-[#10121f] to-[#141726] p-4">
      <div className="grid h-11 w-11 place-items-center rounded-2xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-100">
        <Target className="h-5 w-5" />
      </div>
      <h2 className="mt-3 text-base font-semibold text-white">Select the area you want to clean</h2>
      <p className="mt-1.5 text-xs leading-5 text-white/55">
        Use AI Detect for an automatic suggestion, or choose Rectangle, Polygon, or Brush to mark the unwanted logo, text, timestamp, or overlay.
      </p>

      <Button variant="accent" className="mt-3 w-full" onClick={onAiDetect} disabled={disabled}>
        <ScanSearch className="h-4 w-4" /> Start with AI Detect
      </Button>
      <p className="mt-2 text-center text-[11px] text-white/40">You can adjust the result before processing.</p>

      <ol className="mt-4 space-y-2 border-t border-white/[.07] pt-3">
        {[
          "Select the unwanted area",
          "Review the mask across the video",
          "Save and generate a preview",
        ].map((step, i) => (
          <li key={step} className="flex items-center gap-2.5 text-xs text-white/60">
            <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full border border-white/15 bg-white/[.04] text-[10px] font-semibold text-white/70">
              {i + 1}
            </span>
            {step}
          </li>
        ))}
      </ol>
    </section>
  );
}
