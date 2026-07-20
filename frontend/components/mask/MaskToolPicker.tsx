"use client";

import { BoxSelect, Brush, Eraser, Pentagon, ScanSearch, Sparkles } from "lucide-react";

import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import type { Tool, useMaskWorkspace } from "@/features/mask/useMaskWorkspace";

type Ws = ReturnType<typeof useMaskWorkspace>;

const TOOLS: { id: Tool; label: string; shortcut: string; icon: React.ElementType; hint: string }[] = [
  { id: "rectangle", label: "Rectangle", shortcut: "R", icon: BoxSelect, hint: "Draw a rectangular area around a fixed watermark." },
  { id: "polygon", label: "Polygon", shortcut: "P", icon: Pentagon, hint: "Create a precise custom-shaped selection." },
  { id: "brush", label: "Brush", shortcut: "B", icon: Brush, hint: "Paint over irregular text or graphics." },
  { id: "eraser", label: "Eraser", shortcut: "E", icon: Eraser, hint: "Remove parts of the current mask." },
];

export function MaskToolPicker({
  ws,
  onAiDetect,
  detecting,
}: {
  ws: Ws;
  onAiDetect: () => void;
  detecting: boolean;
}) {
  const { tool, setTool, readOnly, brushR, setBrushR, brushSoft, setBrushSoft, brushOpacity, setBrushOpacity } = ws;

  return (
    <section className="rounded-2xl border border-white/10 bg-[#10121f] p-3">
      <div className="mb-2.5 flex items-center justify-between px-1">
        <h2 className="text-sm font-semibold text-white/85">Selection tools</h2>
        <span className="text-[10px] uppercase tracking-[.14em] text-white/30">Shortcuts</span>
      </div>

      {/* AI Detect — recommended smart action, visually distinct */}
      <button
        type="button"
        onClick={onAiDetect}
        disabled={detecting || readOnly}
        className={cn(
          "group relative flex w-full items-center gap-3 overflow-hidden rounded-xl border border-cyan-300/25 bg-gradient-to-r from-cyan-300/[.08] to-[#4f7cff]/[.08] p-3 text-left transition hover:border-cyan-300/40 hover:from-cyan-300/[.12] focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:cursor-not-allowed disabled:opacity-60",
        )}
        aria-keyshortcuts="A"
      >
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-cyan-300/15 text-cyan-100">
          <ScanSearch className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5 text-sm font-semibold text-cyan-50">
            AI Detect
            <span className="inline-flex items-center gap-1 rounded-full bg-cyan-300/15 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-cyan-100">
              <Sparkles className="h-2.5 w-2.5" /> Recommended
            </span>
          </span>
          <span className="mt-0.5 block truncate text-xs text-cyan-100/60">
            Let ClearFrame suggest likely logos and overlays.
          </span>
        </span>
        <kbd className="shrink-0 rounded border border-cyan-200/20 bg-black/20 px-1.5 py-0.5 font-mono text-[10px] text-cyan-100/70">A</kbd>
      </button>

      <div className="my-2.5 flex items-center gap-2 px-1">
        <span className="h-px flex-1 bg-white/[.07]" />
        <span className="text-[10px] uppercase tracking-wider text-white/25">or draw manually</span>
        <span className="h-px flex-1 bg-white/[.07]" />
      </div>

      <div className="space-y-1">
        {TOOLS.map((item) => {
          const Icon = item.icon;
          const active = tool === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setTool(item.id)}
              disabled={readOnly}
              aria-pressed={active}
              aria-keyshortcuts={item.shortcut}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl border p-2.5 text-left transition focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:cursor-not-allowed disabled:opacity-40",
                active
                  ? "border-[#4f7cff]/40 bg-[#4f7cff]/15"
                  : "border-transparent hover:border-white/10 hover:bg-white/5",
              )}
            >
              <span
                className={cn(
                  "grid h-8 w-8 shrink-0 place-items-center rounded-lg",
                  active ? "bg-[#4f7cff]/25 text-white" : "bg-white/[.04] text-white/55",
                )}
              >
                <Icon className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className={cn("block text-sm font-medium", active ? "text-white" : "text-white/75")}>{item.label}</span>
                <span className="mt-0.5 block truncate text-[11px] text-white/40">{item.hint}</span>
              </span>
              <kbd className="shrink-0 rounded border border-white/10 bg-black/15 px-1.5 py-0.5 font-mono text-[10px] text-white/40">{item.shortcut}</kbd>
            </button>
          );
        })}
      </div>

      {tool === "polygon" && (
        <p className="mt-2.5 px-1 text-xs leading-5 text-white/45">Click each corner, then double-click to close the shape. Press Esc to cancel.</p>
      )}
      {tool === "eraser" && (
        <p className="mt-2.5 px-1 text-xs leading-5 text-white/45">Click the canvas to remove the most recent shape.</p>
      )}

      {tool === "brush" && (
        <div className="mt-3 space-y-3 border-t border-white/10 pt-3">
          <BrushSlider label="Brush size" value={brushR} suffix="px" min={2} max={80} onChange={setBrushR} />
          <BrushSlider label="Softness" value={brushSoft} suffix="px" min={0} max={32} onChange={setBrushSoft} />
          <BrushSlider label="Opacity" value={Math.round(brushOpacity * 100)} suffix="%" min={10} max={100} onChange={(v) => setBrushOpacity(v / 100)} />
        </div>
      )}
    </section>
  );
}

function BrushSlider({
  label,
  value,
  suffix,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  suffix: string;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs text-white/55">
        <span>{label}</span>
        <span className="rounded-full border border-cyan-300/15 bg-cyan-300/10 px-2 py-0.5 font-mono text-[11px] text-cyan-100">{value}{suffix}</span>
      </div>
      <Slider aria-label={label} min={min} max={max} value={[value]} onValueChange={([v]) => onChange(v)} />
    </div>
  );
}
