"use client";

import type { useMaskWorkspace } from "@/features/mask/useMaskWorkspace";
import type { useAiDetection } from "@/features/mask/useAiDetection";
import type { useProjectCredits } from "@/features/mask/useProjectCredits";
import type { VideoProject, WatermarkCandidate } from "@/types";

import { MaskToolPicker } from "./MaskToolPicker";
import { AIDetectionPanel } from "./AIDetectionPanel";
import { EmptyMaskState } from "./EmptyMaskState";
import { MaskPropertiesPanel } from "./MaskPropertiesPanel";
import { MaskHistoryPanel } from "./MaskHistoryPanel";
import { MaskingTips } from "./MaskingTips";
import { WorkspaceActionBar } from "./WorkspaceActionBar";

type Ws = ReturnType<typeof useMaskWorkspace>;
type Detect = ReturnType<typeof useAiDetection>;
type Credits = ReturnType<typeof useProjectCredits>;

/**
 * The right-hand inspector body. Rendered inside the desktop resizable column
 * and reused verbatim inside the mobile/tablet bottom sheet.
 */
export function InspectorContent({
  ws,
  detect,
  credits,
  project,
  onAiDetect,
  onApprove,
  onDrawManually,
  onSave,
  onDiscard,
  onContinue,
  onPreview,
  onReset,
}: {
  ws: Ws;
  detect: Detect;
  credits: Credits;
  project: VideoProject;
  onAiDetect: () => void;
  onApprove: (c: WatermarkCandidate) => void;
  onDrawManually: () => void;
  onSave: () => void;
  onDiscard: () => void;
  onContinue: () => void;
  onPreview: () => void;
  onReset: () => void;
}) {
  return (
    <div className="space-y-3.5">
      <MaskToolPicker ws={ws} onAiDetect={onAiDetect} detecting={detect.phase === "scanning"} />

      <AIDetectionPanel detect={detect} project={project} onApprove={onApprove} onDrawManually={onDrawManually} />

      {!ws.hasMask && detect.phase === "idle" && (
        <EmptyMaskState onAiDetect={onAiDetect} disabled={ws.readOnly} />
      )}

      {ws.hasMask && <MaskPropertiesPanel ws={ws} />}

      {ws.hasMask && <MaskHistoryPanel ws={ws} onReset={onReset} />}

      <MaskingTips />

      <WorkspaceActionBar
        ws={ws}
        credits={credits}
        onSave={onSave}
        onDiscard={onDiscard}
        onContinue={onContinue}
        onPreview={onPreview}
      />
    </div>
  );
}
