"use client";

import { BoxSelect, Check, LoaderCircle, ScanSearch, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { confidenceOf, type useAiDetection } from "@/features/mask/useAiDetection";
import type { VideoProject, WatermarkCandidate } from "@/types";
import { cn } from "@/lib/utils";

type Detect = ReturnType<typeof useAiDetection>;

const TONE: Record<string, string> = {
  strong: "bg-emerald-400/10 text-emerald-300 border-emerald-400/20",
  possible: "bg-amber-400/10 text-amber-200 border-amber-400/20",
  low: "bg-white/[.06] text-white/55 border-white/10",
};

export function AIDetectionPanel({
  detect,
  project,
  onApprove,
  onDrawManually,
}: {
  detect: Detect;
  project: VideoProject;
  onApprove: (candidate: WatermarkCandidate) => void;
  onDrawManually: () => void;
}) {
  if (detect.phase === "idle") return null;

  return (
    <section className="rounded-2xl border border-cyan-300/20 bg-cyan-300/[.04] p-3.5" aria-live="polite">
      <div className="flex items-center justify-between">
        <h2 className="inline-flex items-center gap-2 text-sm font-semibold text-cyan-50">
          <ScanSearch className="h-4 w-4" /> AI detection
        </h2>
        {detect.phase !== "scanning" && (
          <button
            type="button"
            onClick={detect.dismiss}
            aria-label="Dismiss AI detection"
            className="grid h-7 w-7 place-items-center rounded-lg text-white/40 hover:bg-white/5 hover:text-white"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {detect.phase === "scanning" && (
        <div className="mt-3">
          <p className="text-xs leading-5 text-white/60">Analyzing frames for persistent logos, text, and overlays…</p>
          <div className="mt-2.5 flex items-center gap-2">
            <LoaderCircle className="h-4 w-4 shrink-0 animate-spin text-cyan-300 motion-reduce:animate-none" />
            <Progress value={detect.progress} className="flex-1" />
            <span className="w-9 shrink-0 text-right font-mono text-[11px] text-white/50">{Math.round(detect.progress)}%</span>
          </div>
          <p className="mt-1.5 text-[11px] capitalize text-white/35">{detect.stage}</p>
          <Button variant="ghost" size="sm" className="mt-2 w-full" onClick={detect.cancel}>Cancel</Button>
        </div>
      )}

      {detect.phase === "candidates" && (
        <div className="mt-3 space-y-2.5">
          <p className="text-xs text-white/55">Review each suggestion. Accept one to use it as your mask, or draw manually instead.</p>
          {detect.candidates.map((c, i) => {
            const conf = confidenceOf(c);
            const box = c.bounding_box;
            const fw = project.width || 1;
            const fh = project.height || 1;
            return (
              <article key={c.id} className="overflow-hidden rounded-xl border border-white/10 bg-[#12141b]">
                <div className="relative aspect-video overflow-hidden bg-gradient-to-br from-[#0f2032] to-[#171a35]">
                  {project.thumbnail_url ? (
                    <img src={project.thumbnail_url} alt="" className="h-full w-full object-contain" />
                  ) : (
                    <ScanSearch className="absolute left-1/2 top-1/2 h-8 w-8 -translate-x-1/2 -translate-y-1/2 text-white/15" />
                  )}
                  <div
                    className="absolute border-2 border-dashed border-cyan-300 bg-cyan-300/20"
                    style={{
                      left: `${Math.max(0, (box.x / fw) * 100)}%`,
                      top: `${Math.max(0, (box.y / fh) * 100)}%`,
                      width: `${Math.min(100, (box.w / fw) * 100)}%`,
                      height: `${Math.min(100, (box.h / fh) * 100)}%`,
                    }}
                  />
                  <span className="absolute left-2 top-2 rounded-full border border-white/10 bg-black/65 px-2 py-0.5 text-[10px] font-medium text-white/80">
                    Suggestion {i + 1}
                  </span>
                </div>
                <div className="p-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-xs font-medium capitalize text-white/80">{c.candidate_type.replace(/_/g, " ")}</span>
                    <span className={cn("shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold", TONE[conf.tone])}>{conf.label}</span>
                  </div>
                  <div className="mt-2 flex gap-2">
                    <Button variant="primary" size="sm" className="flex-1" onClick={() => onApprove(c)} disabled={detect.approvingId !== null}>
                      {detect.approvingId === c.id ? <LoaderCircle className="h-4 w-4 animate-spin motion-reduce:animate-none" /> : <Check className="h-4 w-4" />}
                      Accept
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => detect.reject(c.id)} disabled={detect.approvingId !== null}>
                      Reject
                    </Button>
                  </div>
                </div>
              </article>
            );
          })}
          <Button variant="secondary" size="sm" className="w-full" onClick={onDrawManually}>
            <BoxSelect className="h-4 w-4" /> Draw manually instead
          </Button>
        </div>
      )}

      {detect.phase === "empty" && (
        <div className="mt-3 rounded-xl border border-white/10 bg-black/20 p-3 text-center">
          <p className="text-xs leading-5 text-white/60">
            We couldn&apos;t confidently detect an overlay. Try drawing the area manually with Rectangle or Brush.
          </p>
          <div className="mt-3 flex gap-2">
            <Button variant="accent" size="sm" className="flex-1" onClick={() => detect.run(true)}>Run again</Button>
            <Button variant="primary" size="sm" className="flex-1" onClick={onDrawManually}>
              <BoxSelect className="h-4 w-4" /> Draw manually
            </Button>
          </div>
        </div>
      )}

      {detect.phase === "error" && (
        <div className="mt-3 rounded-xl border border-rose-400/20 bg-rose-500/10 p-3">
          <p className="text-xs leading-5 text-rose-200">{detect.error} Your work is safe.</p>
          <div className="mt-2.5 flex gap-2">
            <Button variant="secondary" size="sm" className="flex-1" onClick={() => detect.run(true)}>Retry</Button>
            <Button variant="primary" size="sm" className="flex-1" onClick={onDrawManually}>
              <BoxSelect className="h-4 w-4" /> Draw manually
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
