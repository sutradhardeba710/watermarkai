"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useHotkeys } from "react-hotkeys-hook";
import { Group as PanelGroup, Panel, Separator as PanelResizeHandle } from "react-resizable-panels";
import { BoxSelect, Brush, Eraser, Pentagon, PanelRightOpen, Redo2, ScanSearch, Undo2 } from "lucide-react";
import { toast } from "sonner";

import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { useMaskWorkspace } from "@/features/mask/useMaskWorkspace";
import { useAiDetection } from "@/features/mask/useAiDetection";
import { useProjectCredits } from "@/features/mask/useProjectCredits";
import type { WatermarkCandidate } from "@/types";

import { MaskWorkspaceHeader } from "@/components/mask/MaskWorkspaceHeader";
import { VideoCanvas } from "@/components/mask/VideoCanvas";
import { PlaybackControls } from "@/components/mask/PlaybackControls";
import { EditingTimeline } from "@/components/mask/EditingTimeline";
import { InspectorContent } from "@/components/mask/InspectorContent";
import { ConfirmResetDialog } from "@/components/mask/ConfirmResetDialog";
import { FirstTimeMaskingTour } from "@/components/mask/FirstTimeMaskingTour";
import { WorkspaceErrorState, OfflineBanner } from "@/components/mask/WorkspaceErrorState";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

const MOBILE_TOOLS = [
  { id: "rectangle" as const, label: "Rectangle", icon: BoxSelect },
  { id: "polygon" as const, label: "Polygon", icon: Pentagon },
  { id: "brush" as const, label: "Brush", icon: Brush },
  { id: "eraser" as const, label: "Eraser", icon: Eraser },
];

function MobileMaskToolbar({ ws, detecting, onAiDetect }: { ws: ReturnType<typeof useMaskWorkspace>; detecting: boolean; onAiDetect: () => void }) {
  return <div className="mobile-scroll -mx-3 overflow-x-auto border-y border-white/10 bg-[#0c0e1a] px-3 py-2" aria-label="Mask tools"><div className="flex w-max gap-2"><button type="button" onClick={onAiDetect} disabled={detecting || ws.readOnly} className="flex min-h-14 min-w-[5.25rem] flex-col items-center justify-center gap-1 rounded-xl border border-cyan-300/25 bg-cyan-300/10 px-3 text-xs font-medium text-cyan-100 disabled:opacity-50"><ScanSearch className="h-5 w-5" />{detecting ? "Detecting" : "AI Detect"}</button>{MOBILE_TOOLS.map(({ id, label, icon: Icon }) => <button type="button" key={id} onClick={() => ws.setTool(id)} disabled={ws.readOnly} aria-pressed={ws.tool === id} className={`flex min-h-14 min-w-[4.75rem] flex-col items-center justify-center gap-1 rounded-xl border px-3 text-xs font-medium ${ws.tool === id ? "border-[#4f7cff]/50 bg-[#4f7cff]/20 text-white" : "border-white/10 bg-white/[.03] text-white/65"}`}><Icon className="h-5 w-5" />{label}</button>)}<button type="button" onClick={ws.undo} disabled={ws.readOnly} className="grid h-14 w-14 place-items-center rounded-xl border border-white/10 text-white/65 disabled:opacity-30" aria-label="Undo"><Undo2 className="h-5 w-5" /></button><button type="button" onClick={ws.redo} disabled={ws.readOnly} className="grid h-14 w-14 place-items-center rounded-xl border border-white/10 text-white/65 disabled:opacity-30" aria-label="Redo"><Redo2 className="h-5 w-5" /></button></div></div>;
}

export default function ProjectWorkspace() {
  useHydrateAuth();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = params.id;

  const ws = useMaskWorkspace(projectId);
  const detect = useAiDetection(projectId);
  const credits = useProjectCredits();

  const [resetOpen, setResetOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [showTour, setShowTour] = useState(false);
  const [offline, setOffline] = useState(false);
  const [spacePan, setSpacePan] = useState(false);
  // The canvas block (video + mask canvas) binds the workspace's single
  // videoRef/canvasRef. It MUST be mounted exactly once — rendering it in both
  // a desktop and a mobile layout at the same time makes both copies claim the
  // same refs, so the ref points at the hidden copy and play/pause + drawing
  // silently act on a 0x0 element. Mount one layout at a time instead.
  const [isDesktop, setIsDesktop] = useState(true);

  // --- Connectivity ---
  useEffect(() => {
    setOffline(typeof navigator !== "undefined" && !navigator.onLine);
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  // --- Responsive layout (mount exactly one copy of the canvas block) ---
  // Matches Tailwind's `lg` breakpoint (1024px). Kept in JS instead of CSS
  // `hidden`/`lg:block` so only one video/canvas is ever in the DOM.
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const apply = () => setIsDesktop(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  // --- Keyboard shortcuts (skip when typing in a field) ---
  const opts = { enableOnFormTags: false as const, preventDefault: true };
  useHotkeys("a", () => detect.run(false), opts, [detect]);
  useHotkeys("r", () => ws.setTool("rectangle"), opts, [ws]);
  useHotkeys("p", () => ws.setTool("polygon"), opts, [ws]);
  useHotkeys("b", () => ws.setTool("brush"), opts, [ws]);
  useHotkeys("e", () => ws.setTool("eraser"), opts, [ws]);
  useHotkeys("v", () => ws.setTool("pan"), opts, [ws]);
  useHotkeys("mod+z", () => ws.undo(), opts, [ws]);
  useHotkeys("mod+shift+z", () => ws.redo(), opts, [ws]);
  useHotkeys("escape", () => { ws.cancelDrawing(); detect.dismiss(); }, opts, [ws, detect]);
  // Hold Space for temporary pan.
  useHotkeys("space", () => setSpacePan(true), { ...opts, keydown: true }, []);
  useHotkeys("space", () => setSpacePan(false), { ...opts, keyup: true }, []);

  // --- Actions ---
  const handleSave = useCallback(async () => {
    const ok = await ws.save();
    if (ok) toast.success("Mask saved. Preview and processing are unlocked.");
  }, [ws]);

  const handleDiscard = useCallback(() => {
    ws.resetMask();
    toast.message("Changes discarded.");
  }, [ws]);

  const handleContinue = useCallback(() => {
    router.push(`/projects/${projectId}/result`);
  }, [router, projectId]);

  const handlePreview = useCallback(() => {
    router.push(`/projects/${projectId}/result`);
  }, [router, projectId]);

  const handleApprove = useCallback(
    async (candidate: WatermarkCandidate) => {
      const mask = await detect.approve(candidate);
      if (mask) {
        ws.applyLoadedMask(mask);
        toast.success("AI suggestion applied as your mask.");
      }
    },
    [detect, ws],
  );

  const handleDrawManually = useCallback(() => {
    detect.dismiss();
    ws.setTool("rectangle");
  }, [detect, ws]);

  // --- Error / gate states ---
  if (ws.loadError && !ws.project) {
    return (
      <WorkspaceErrorState
        kind="load-error"
        message={ws.loadError}
        referenceId={`PROJ-${projectId.slice(0, 8)}`}
        onRetry={() => window.location.reload()}
      />
    );
  }

  if (!ws.project) {
    return (
      <main className="grid min-h-dvh place-items-center bg-[#07080f] text-white/50">
        <div className="flex flex-col items-center gap-3">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-cyan-300 motion-reduce:animate-none" />
          Loading workspace…
        </div>
      </main>
    );
  }

  if (ws.project.status === "expired") {
    return <WorkspaceErrorState kind="expired" />;
  }

  const project = ws.project;

  const desktopCanvas = (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <VideoCanvas ws={ws} detecting={detect.phase === "scanning"} panMode={spacePan} />
      <PlaybackControls ws={ws} />
      <EditingTimeline ws={ws} hasMask={ws.hasMask} />
      <p className="text-center text-sm text-white/45">{ws.hasMask ? "Scrub through the video to confirm the mask at several timestamps." : "Select the unwanted logo, text, or overlay to begin."}</p>
    </div>
  );

  const inspector = (
    <InspectorContent
      ws={ws}
      detect={detect}
      credits={credits}
      project={project}
      onAiDetect={() => detect.run(false)}
      onApprove={handleApprove}
      onDrawManually={handleDrawManually}
      onSave={handleSave}
      onDiscard={handleDiscard}
      onContinue={handleContinue}
      onPreview={handlePreview}
      onReset={() => setResetOpen(true)}
    />
  );

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-[#07080f] text-white">
      {offline && <OfflineBanner reconnecting={false} />}

      <MaskWorkspaceHeader
        project={project}
        saveState={ws.saveState}
        onRetrySave={handleSave}
        onHelp={() => setShowTour(true)}
        maskSaved={ws.maskSaved}
        onStepClick={(index) => {
          if (index === 1) router.push(`/projects/${projectId}/candidates`);
        }}
      />

      {/* Desktop: resizable two-column. Rendered only when isDesktop so the
          canvas block (and its refs) exists exactly once. */}
      {isDesktop ? (
        <div className="min-h-0 flex-1">
          <PanelGroup orientation="horizontal" className="h-full px-4 py-4">
            <Panel defaultSize="72%" minSize="55%" className="pr-4">
              {desktopCanvas}
            </Panel>
            <PanelResizeHandle className="group w-1.5 shrink-0 rounded-full bg-white/5 transition hover:bg-cyan-300/30 data-[resize-handle-active]:bg-cyan-300/50" />
            <Panel defaultSize="28%" minSize="22%" maxSize="36%" className="pl-4">
              <div className="h-full overflow-y-auto pr-1" style={{ maxHeight: "calc(100dvh - 8rem)" }}>
                {inspector}
              </div>
            </Panel>
          </PanelGroup>
        </div>
      ) : (
        /* Tablet / mobile: video on top, inspector in a bottom sheet */
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-3 pb-24">
          <div className="h-[min(42dvh,26rem)] min-h-[12rem] sm:min-h-[18rem]">
            <VideoCanvas ws={ws} detecting={detect.phase === "scanning"} panMode={spacePan} />
          </div>
          <div className="mt-3 space-y-3">
            <MobileMaskToolbar ws={ws} detecting={detect.phase === "scanning"} onAiDetect={() => detect.run(false)} />
            <PlaybackControls ws={ws} />
            <EditingTimeline ws={ws} hasMask={ws.hasMask} />
            <p className="text-center text-sm leading-6 text-white/45">{ws.hasMask ? "Scrub through several timestamps to confirm the mask stays aligned." : "Choose a tool, then select the unwanted logo, text, or overlay."}</p>
          </div>
          <div className="fixed inset-x-0 bottom-0 z-20 border-t border-white/10 bg-[#07080f]/95 px-3 py-2.5 pb-[max(.625rem,env(safe-area-inset-bottom))] backdrop-blur lg:hidden">
            <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
              <SheetTrigger asChild>
                <Button variant="primary" className="w-full">
                  <PanelRightOpen className="h-4 w-4" /> Open tools &amp; mask options
                </Button>
              </SheetTrigger>
              <SheetContent side="bottom" className="px-4 pb-[calc(1.5rem+env(safe-area-inset-bottom))] pt-5" aria-describedby={undefined}>
                <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-white/15" />
                <SheetTitle className="mb-3 text-sm font-semibold text-white/85">Mask workspace</SheetTitle>
                {inspector}
              </SheetContent>
            </Sheet>
          </div>
        </div>
      )}

      <ConfirmResetDialog open={resetOpen} onOpenChange={setResetOpen} onConfirm={ws.resetMask} />
      <FirstTimeMaskingTour forceOpen={showTour} onClose={() => setShowTour(false)} />
    </div>
  );
}
