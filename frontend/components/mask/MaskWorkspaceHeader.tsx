"use client";

import Link from "next/link";
import { CircleHelp, LogOut, Sparkles } from "lucide-react";

import { WorkflowStepper, WORKFLOW_PHASES, type StepStatus } from "@/components/WorkflowStepper";
import { Button } from "@/components/ui/button";
import { InfoTip, TooltipProvider } from "@/components/ui/tooltip";
import type { VideoProject } from "@/types";
import type { SaveState } from "@/features/mask/useMaskWorkspace";
import { ProjectMetadata } from "./ProjectMetadata";
import { SaveStatus } from "./SaveStatus";

export function MaskWorkspaceHeader({
  project,
  saveState,
  onRetrySave,
  onHelp,
  maskSaved,
  onStepClick,
}: {
  project: VideoProject;
  saveState: SaveState;
  onRetrySave: () => void;
  onHelp: () => void;
  maskSaved: boolean;
  onStepClick: (index: number) => void;
}) {
  // Mask is step index 2. Steps before are complete; Track becomes available
  // once the mask is saved, otherwise upcoming; later steps stay locked.
  const statusOf = (index: number): StepStatus => {
    if (index < 2) return "complete";
    if (index === 2) return "current";
    if (index === 3) return maskSaved ? "upcoming" : "locked";
    return "locked";
  };

  return (
    <TooltipProvider delayDuration={120}>
      <header className="sticky top-0 z-30 border-b border-white/[.07] bg-[#07080f]/95 backdrop-blur-xl">
        <div className="flex items-center gap-3 px-4 py-2.5 sm:px-6">
          <Link
            href="/dashboard"
            className="flex shrink-0 items-center gap-2 text-sm font-semibold tracking-tight text-white"
          >
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6]">
              <Sparkles className="h-4 w-4" />
            </span>
            <span className="hidden sm:inline">ClearFrame</span>
          </Link>

          <div className="mx-1 hidden h-6 w-px bg-white/10 sm:block" />

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1
                className="truncate text-sm font-semibold text-white/90"
                title={project.title || project.original_filename}
              >
                {project.title || project.original_filename}
              </h1>
              <span className="hidden rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-cyan-100 md:inline">
                Mask
              </span>
            </div>
            <div className="mt-0.5 flex items-center gap-3">
              <SaveStatus state={saveState} onRetry={onRetrySave} />
              <span className="hidden text-white/15 sm:inline">·</span>
              <ProjectMetadata project={project} className="hidden sm:flex" />
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-1.5">
            <InfoTip label="Masking help and keyboard shortcuts" side="bottom">
              <Button variant="ghost" size="icon" aria-label="Help" onClick={onHelp}>
                <CircleHelp className="h-4 w-4" />
              </Button>
            </InfoTip>
            <Button variant="secondary" size="sm" asChild>
              <Link href="/dashboard">
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Exit</span>
              </Link>
            </Button>
          </div>
        </div>

        <div className="px-3 pb-3 sm:px-6">
          <WorkflowStepper
            current={2}
            phases={WORKFLOW_PHASES as readonly string[]}
            statusOf={statusOf}
            onStepClick={onStepClick}
          />
        </div>
      </header>
    </TooltipProvider>
  );
}
