"use client";

import { Check, LoaderCircle, PencilLine, RefreshCw, TriangleAlert } from "lucide-react";

import type { SaveState } from "@/features/mask/useMaskWorkspace";
import { cn } from "@/lib/utils";

const MAP: Record<SaveState, { icon: React.ElementType; text: string; className: string; spin?: boolean }> = {
  clean: { icon: Check, text: "All changes saved", className: "text-white/45" },
  saved: { icon: Check, text: "All changes saved", className: "text-emerald-300" },
  dirty: { icon: PencilLine, text: "Unsaved changes", className: "text-amber-200/90" },
  saving: { icon: LoaderCircle, text: "Saving…", className: "text-cyan-200", spin: true },
  error: { icon: TriangleAlert, text: "Couldn't save", className: "text-rose-300" },
};

export function SaveStatus({
  state,
  onRetry,
  className,
}: {
  state: SaveState;
  onRetry?: () => void;
  className?: string;
}) {
  const cfg = MAP[state];
  const Icon = cfg.icon;
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("inline-flex items-center gap-1.5 text-xs font-medium", cfg.className, className)}
    >
      <Icon className={cn("h-3.5 w-3.5", cfg.spin && "animate-spin motion-reduce:animate-none")} />
      <span>{cfg.text}</span>
      {state === "error" && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="ml-1 inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-rose-200 underline underline-offset-2 hover:bg-rose-400/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
        >
          <RefreshCw className="h-3 w-3" /> Retry
        </button>
      )}
    </div>
  );
}
