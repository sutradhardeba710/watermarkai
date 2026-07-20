"use client";

import { Check, Lock, TriangleAlert } from "lucide-react";

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export const WORKFLOW_PHASES = ["Upload", "Detect", "Mask", "Track", "Preview", "Export"] as const;

/** Short explanation shown on hover/focus for each workflow step. */
export const WORKFLOW_DESCRIPTIONS: Record<string, string> = {
  Upload: "Video uploaded successfully",
  Detect: "AI analysis completed",
  Mask: "Select or correct the area to remove",
  Track: "Follow the selected area across frames",
  Preview: "Review the cleaned result",
  Export: "Render and download the final video",
};

export type StepStatus = "complete" | "current" | "upcoming" | "locked" | "warning";

/**
 * Shared workflow progress indicator. Backwards compatible: passing only
 * `current` reproduces the original behaviour (steps before are complete, after
 * are upcoming). Optional props layer on richer status, hover explanations, and
 * safe click-to-navigate for completed steps.
 */
export function WorkflowStepper({
  current,
  phases = WORKFLOW_PHASES as readonly string[],
  descriptions = WORKFLOW_DESCRIPTIONS,
  statusOf,
  onStepClick,
  className,
}: {
  current: number;
  phases?: readonly string[];
  descriptions?: Record<string, string>;
  statusOf?: (index: number) => StepStatus;
  onStepClick?: (index: number) => void;
  className?: string;
}) {
  const resolveStatus = (index: number): StepStatus => {
    if (statusOf) return statusOf(index);
    if (index < current) return "complete";
    if (index === current) return "current";
    return "upcoming";
  };

  return (
    <TooltipProvider delayDuration={120}>
      <nav
        aria-label="Project workflow progress"
        className={cn(
          "rounded-2xl border border-white/10 bg-[#0e101d] p-3 sm:px-5 sm:py-4",
          className,
        )}
      >
        <ol className="flex items-center">
          {phases.map((phase, index) => {
            const status = resolveStatus(index);
            const isLast = index === phases.length - 1;
            const description = descriptions[phase];
            const clickable =
              typeof onStepClick === "function" && (status === "complete" || status === "warning");

            const node = (
              <span
                aria-hidden="true"
                className={cn(
                  "grid h-8 w-8 shrink-0 place-items-center rounded-full text-[13px] font-semibold transition-colors",
                  status === "current" && "bg-cyan-300 text-[#06121a] ring-4 ring-cyan-300/20 shadow-[0_0_18px_rgba(34,211,238,.45)]",
                  status === "complete" && "bg-gradient-to-br from-[#4f7cff] to-[#8b5cf6] text-white shadow-[0_2px_10px_rgba(109,94,247,.4)]",
                  status === "warning" && "bg-amber-400 text-[#1a1204]",
                  status === "upcoming" && "border border-white/12 bg-white/[.04] text-white/40",
                  status === "locked" && "border border-white/[.07] bg-white/[.02] text-white/25",
                )}
              >
                {status === "complete" ? (
                  <Check className="h-4 w-4" />
                ) : status === "warning" ? (
                  <TriangleAlert className="h-4 w-4" />
                ) : status === "locked" ? (
                  <Lock className="h-3.5 w-3.5" />
                ) : (
                  index + 1
                )}
              </span>
            );

            const label = (
              <span
                aria-current={status === "current" ? "step" : undefined}
                className={cn(
                  "hidden truncate text-sm font-medium sm:block",
                  status === "current" && "text-white",
                  status === "complete" && "text-white/70",
                  status === "warning" && "text-amber-200/90",
                  status === "upcoming" && "text-white/35",
                  status === "locked" && "text-white/25",
                )}
              >
                {phase}
              </span>
            );

            const inner = (
              <div className="flex min-w-0 items-center gap-2.5">
                {node}
                {label}
              </div>
            );

            return (
              <li key={phase} className="flex flex-1 items-center last:flex-none">
                {description ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      {clickable ? (
                        <button
                          type="button"
                          onClick={() => onStepClick?.(index)}
                          className="rounded-xl outline-none transition focus-visible:ring-2 focus-visible:ring-cyan-300"
                        >
                          {inner}
                        </button>
                      ) : (
                        <div
                          tabIndex={0}
                          className="cursor-default rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/50"
                        >
                          {inner}
                        </div>
                      )}
                    </TooltipTrigger>
                    <TooltipContent side="bottom">
                      <p className="font-medium text-white/90">{phase}</p>
                      <p className="mt-0.5 text-white/60">{description}</p>
                      {clickable && <p className="mt-1 text-cyan-200/80">Click to revisit this step</p>}
                    </TooltipContent>
                  </Tooltip>
                ) : (
                  inner
                )}
                {!isLast && (
                  <span
                    aria-hidden="true"
                    className="mx-2 h-px flex-1 rounded-full sm:mx-3"
                    style={{
                      background:
                        status === "complete"
                          ? "linear-gradient(to right,#4f7cff,#8b5cf6)"
                          : status === "current"
                            ? "linear-gradient(to right,#22d3ee,rgba(255,255,255,.08))"
                            : "rgba(255,255,255,.08)",
                    }}
                  />
                )}
              </li>
            );
          })}
        </ol>
      </nav>
    </TooltipProvider>
  );
}
