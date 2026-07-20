"use client";

import { Info, Layers, RotateCcw } from "lucide-react";

import { Slider } from "@/components/ui/slider";
import { InfoTip, TooltipProvider } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import type { useMaskWorkspace } from "@/features/mask/useMaskWorkspace";
import { cn } from "@/lib/utils";

type Ws = ReturnType<typeof useMaskWorkspace>;

export function MaskPropertiesPanel({ ws }: { ws: Ws }) {
  const {
    hasMask,
    maskExpansion,
    maskFeathering,
    temporalSmoothing,
    updateExpansion,
    updateFeather,
    updateTemporal,
    resetProperties,
    scaledExpansion,
    readOnly,
  } = ws;

  const disabled = !hasMask || readOnly;

  return (
    <TooltipProvider delayDuration={150}>
      <section className={cn("rounded-2xl border border-white/10 bg-[#10121f] p-4", disabled && "opacity-95")}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white/85">Mask properties</h2>
          {hasMask && !readOnly && (
            <InfoTip label="Reset all properties to defaults">
              <button
                type="button"
                onClick={resetProperties}
                aria-label="Reset properties to defaults"
                className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-white/45 hover:bg-white/5 hover:text-white"
              >
                <RotateCcw className="h-3 w-3" /> Reset
              </button>
            </InfoTip>
          )}
        </div>

        {disabled && (
          <p className="mt-2 rounded-lg border border-white/[.07] bg-black/20 px-3 py-2 text-xs leading-5 text-white/45">
            {readOnly
              ? "This project is read-only, so adjustments are disabled."
              : "Create or accept a mask first — these adjustments shape the area you selected."}
          </p>
        )}

        <div className={cn("mt-4 space-y-5", disabled && "pointer-events-none opacity-40")}>
          <PropSlider
            label="Expand or shrink"
            help="Adjust how far the mask extends beyond the selected area. Positive grows it; negative shrinks it."
            value={maskExpansion}
            min={-40}
            max={80}
            suffix="px"
            onChange={updateExpansion}
            footnote={`Preview display expansion: ≈${scaledExpansion}px`}
          />
          <PropSlider
            label="Feather"
            help="Softens the mask edge to reduce visible seams between the cleaned area and the rest of the frame."
            value={maskFeathering}
            min={0}
            max={32}
            suffix="px"
            onChange={updateFeather}
          />

          <div className="rounded-xl border border-white/[.08] bg-black/10 p-3">
            <label className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                checked={temporalSmoothing}
                onChange={(e) => updateTemporal(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-cyan-300"
              />
              <span className="min-w-0">
                <span className="flex items-center gap-1.5 text-sm font-medium text-white/80">
                  Temporal smoothing
                  <InfoTip label="Keeps the removed area steady across nearby frames so it doesn't flicker or shimmer as the video plays.">
                    <Info className="h-3 w-3 text-white/35" />
                  </InfoTip>
                </span>
                <span className="mt-1 block text-xs leading-5 text-white/45">
                  Keeps the removed area steady across nearby frames so it doesn&apos;t flicker.
                </span>
              </span>
            </label>
            {temporalSmoothing && (
              <div className="mt-2.5 flex items-center gap-1.5 border-t border-white/10 pt-2.5 text-[11px] text-cyan-100/70">
                <Layers className="h-3.5 w-3.5" />
                <span>Applied across neighbouring frames</span>
                <span className="ml-1 flex gap-0.5">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <span key={i} className={cn("h-3 w-1.5 rounded-sm", i === 2 ? "bg-cyan-300" : "bg-cyan-300/25")} />
                  ))}
                </span>
              </div>
            )}
          </div>
        </div>
      </section>
    </TooltipProvider>
  );
}

function PropSlider({
  label,
  help,
  value,
  min,
  max,
  suffix,
  onChange,
  footnote,
}: {
  label: string;
  help: string;
  value: number;
  min: number;
  max: number;
  suffix: string;
  onChange: (v: number) => void;
  footnote?: string;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs text-white/60">
          {label}
          <InfoTip label={help}>
            <Info className="h-3 w-3 text-white/30" />
          </InfoTip>
        </span>
        <input
          type="number"
          aria-label={`${label} value`}
          value={value}
          min={min}
          max={max}
          onChange={(e) => {
            const v = Number(e.target.value);
            if (Number.isFinite(v)) onChange(Math.max(min, Math.min(max, v)));
          }}
          className="h-7 w-16 rounded-md border border-white/10 bg-black/20 px-2 text-right font-mono text-[11px] text-cyan-100 outline-none focus:border-cyan-300/40 focus-visible:ring-1 focus-visible:ring-cyan-300/40"
        />
      </div>
      <Slider aria-label={label} min={min} max={max} value={[value]} onValueChange={([v]) => onChange(v)} />
      {footnote && <p className="mt-1.5 text-[11px] text-white/35">{footnote}</p>}
      <span className="sr-only">{suffix}</span>
    </div>
  );
}
