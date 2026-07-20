"use client";

import {
  Brush,
  Check,
  Eraser,
  History,
  Redo2,
  RotateCcw,
  Scan,
  Sliders,
  Trash2,
  Undo2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type { HistoryEntry, useMaskWorkspace } from "@/features/mask/useMaskWorkspace";
import { cn } from "@/lib/utils";

type Ws = ReturnType<typeof useMaskWorkspace>;

const KIND_ICON: Record<HistoryEntry["kind"], React.ElementType> = {
  create: Brush,
  adjust: Sliders,
  erase: Eraser,
  reset: RotateCcw,
  detect: Scan,
};

export function MaskHistoryPanel({ ws, onReset }: { ws: Ws; onReset: () => void }) {
  const { history, undo, redo, shapes, redoStack, readOnly } = ws;
  const recent = [...history].slice(-6).reverse();

  return (
    <section className="rounded-2xl border border-white/10 bg-[#10121f] p-4">
      <div className="flex items-center justify-between">
        <h2 className="inline-flex items-center gap-2 text-sm font-semibold text-white/85">
          <History className="h-4 w-4 text-white/50" /> History
        </h2>
        <span className="text-[11px] text-white/35">{shapes.length} {shapes.length === 1 ? "shape" : "shapes"}</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <Button variant="secondary" size="sm" onClick={undo} disabled={!shapes.length || readOnly}>
          <Undo2 className="h-4 w-4" /> Undo
        </Button>
        <Button variant="secondary" size="sm" onClick={redo} disabled={!redoStack.length || readOnly}>
          <Redo2 className="h-4 w-4" /> Redo
        </Button>
      </div>

      <div className="mt-3 min-h-[3rem]">
        {recent.length === 0 ? (
          <p className="rounded-lg border border-dashed border-white/10 px-3 py-3 text-center text-xs text-white/35">
            No mask changes yet
          </p>
        ) : (
          <ul className="space-y-1">
            {recent.map((entry) => {
              const Icon = KIND_ICON[entry.kind];
              return (
                <li key={entry.id} className="flex items-center gap-2 rounded-lg px-1.5 py-1 text-xs text-white/60">
                  <span className={cn("grid h-5 w-5 shrink-0 place-items-center rounded-md bg-white/[.05]", entry.kind === "reset" && "text-rose-300/70")}>
                    <Icon className="h-3 w-3" />
                  </span>
                  <span className="truncate">{entry.label}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="mt-2 border-t border-white/[.07] pt-2">
        <Button variant="danger" size="sm" className="w-full" onClick={onReset} disabled={!shapes.length || readOnly}>
          <Trash2 className="h-4 w-4" /> Reset mask
        </Button>
      </div>
    </section>
  );
}
