"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Hand,
  Maximize,
  Minimize2,
  RotateCcw,
  ScanSearch,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { InfoTip, TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { useMaskWorkspace } from "@/features/mask/useMaskWorkspace";

type Ws = ReturnType<typeof useMaskWorkspace>;

const MIN_ZOOM = 1;
const MAX_ZOOM = 4;

function videoErrorReason(code: number | null): string {
  return code === 4
    ? "The source could not be found. The proxy may still be generating."
    : code === 3
      ? "Your browser could not decode this video."
      : code === 2
        ? "A network error interrupted playback."
        : code === 1
          ? "Playback was aborted."
          : "An unexpected playback error occurred.";
}

export function VideoCanvas({
  ws,
  detecting,
  panMode,
  children,
}: {
  ws: Ws;
  detecting: boolean;
  panMode: boolean;
  children?: React.ReactNode;
}) {
  const {
    project,
    proxyUrl,
    videoRef,
    canvasRef,
    containerRef,
    onPointerDown,
    onPointerMove,
    endDraw,
    onDoubleClick,
    setCurrentTime,
    setDuration,
    setPlaying,
    videoError,
    setVideoError,
    setVideoErrorCode,
    videoErrorCode,
    videoLoading,
    setVideoLoading,
    readOnly,
    tool,
  } = ws;

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const panRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  const usePan = panMode || tool === "pan";

  const resetView = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const changeZoom = useCallback((next: number) => {
    const z = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, next));
    setZoom(z);
    if (z === 1) setPan({ x: 0, y: 0 });
  }, []);

  const onWheel = useCallback(
    (e: React.WheelEvent) => {
      if (!usePan && !e.ctrlKey) return;
      e.preventDefault();
      changeZoom(zoom + (e.deltaY < 0 ? 0.2 : -0.2));
    },
    [usePan, zoom, changeZoom],
  );

  // Pan drag when the pan tool is active (does not touch mask coordinates).
  const onCanvasPointerDown = (e: React.PointerEvent) => {
    if (usePan && zoom > 1) {
      panRef.current = { x: e.clientX, y: e.clientY, ox: pan.x, oy: pan.y };
      (e.target as Element).setPointerCapture?.(e.pointerId);
      return;
    }
    onPointerDown(e);
  };
  const onCanvasPointerMove = (e: React.PointerEvent) => {
    if (panRef.current) {
      setPan({ x: panRef.current.ox + (e.clientX - panRef.current.x), y: panRef.current.oy + (e.clientY - panRef.current.y) });
      return;
    }
    onPointerMove(e);
  };
  const onCanvasPointerUp = (e: React.PointerEvent) => {
    if (panRef.current) {
      panRef.current = null;
      return;
    }
    endDraw();
  };

  const toggleFullscreen = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.();
  }, [containerRef]);

  useEffect(() => {
    const onChange = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const cursor = usePan ? (zoom > 1 ? "grab" : "default") : readOnly ? "default" : "crosshair";

  // Contain-fit: the canvas box must keep the exact video aspect ratio (mask
  // coordinates are mapped through the element box), so it scales down via
  // width = min(panel width, available height × ratio) using container units.
  const ratio = project?.width && project?.height ? project.width / project.height : 16 / 9;

  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <div className="relative min-h-0 flex-1 [container-type:size]">
        <div
          ref={containerRef}
          className="group relative mx-auto flex max-h-full items-center justify-center overflow-hidden rounded-2xl border border-white/10 bg-[#050608] shadow-[0_18px_60px_rgba(0,0,0,.4)]"
          style={{
            aspectRatio: project?.width && project?.height ? `${project.width} / ${project.height}` : "16 / 9",
            width: `min(100%, calc(100cqh * ${ratio}))`,
          }}
        >
          <div
            className="relative h-full w-full origin-center transition-transform duration-100"
            style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
          >
            {proxyUrl ? (
              <video
                ref={videoRef}
                src={proxyUrl}
                className="block h-full w-full object-contain"
                onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                onLoadedMetadata={(e) => {
                  setDuration(e.currentTarget.duration || project?.duration || 0);
                  setVideoLoading(false);
                }}
                onLoadedData={() => setVideoLoading(false)}
                onCanPlay={() => setVideoLoading(false)}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                onError={() => {
                  const code = videoRef.current?.error?.code ?? null;
                  setVideoErrorCode(code);
                  setVideoError(videoErrorReason(code));
                  setVideoLoading(false);
                }}
                onEnded={() => setPlaying(false)}
                playsInline
              />
            ) : (
              <div className="grid h-full w-full place-items-center px-6 text-center text-sm text-white/45">
                Video preview is not available yet. The proxy is still being generated.
              </div>
            )}

            <canvas
              ref={canvasRef}
              aria-label="Interactive video mask canvas"
              className={cn("absolute inset-0 h-full w-full touch-none")}
              style={{ cursor }}
              onPointerDown={onCanvasPointerDown}
              onPointerMove={onCanvasPointerMove}
              onPointerUp={onCanvasPointerUp}
              onPointerCancel={onCanvasPointerUp}
              onDoubleClick={onDoubleClick}
              onWheel={onWheel}
            />
          </div>

          {/* Detection scanning overlay */}
          {detecting && (
            <div className="pointer-events-none absolute inset-0 z-20 overflow-hidden bg-cyan-300/[.035]" aria-hidden="true">
              <div className="mask-scan-line absolute inset-x-0 h-px bg-cyan-200 shadow-[0_0_18px_4px_rgba(34,211,238,.55)]" />
              <div className="absolute left-4 top-4 flex items-center gap-2 rounded-full border border-cyan-300/25 bg-[#071014]/85 px-3 py-1.5 text-xs font-semibold text-cyan-100 backdrop-blur">
                <ScanSearch className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none" /> Analyzing frames
              </div>
            </div>
          )}

          {/* Loading overlay */}
          {proxyUrl && !videoError && videoLoading && !detecting && (
            <div className="pointer-events-none absolute inset-0 z-10 grid place-items-center bg-black/30">
              <div className="flex flex-col items-center gap-3 text-sm text-white/55">
                <span className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-cyan-300 motion-reduce:animate-none" />
                Loading preview…
              </div>
            </div>
          )}

          {/* Error overlay */}
          {videoError && (
            <div className="absolute inset-x-3 bottom-3 z-30 rounded-xl border border-rose-400/25 bg-rose-950/90 px-4 py-3 text-sm text-rose-100 shadow-lg">
              <p className="font-semibold">Video preview unavailable</p>
              <p className="mt-0.5 text-rose-100/80">{videoError} Your mask work is safe.</p>
              <div className="mt-2 flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setVideoError(null);
                    setVideoErrorCode(null);
                    setVideoLoading(true);
                    videoRef.current?.load();
                  }}
                  className="font-semibold underline underline-offset-2"
                >
                  Retry
                </button>
                {videoErrorCode != null && (
                  <span className="text-[11px] text-rose-200/50">Ref: VID-{videoErrorCode}</span>
                )}
              </div>
            </div>
          )}

          {/* Canvas toolbar — top right */}
          <div className="absolute right-3 top-3 z-20 flex items-center gap-1 rounded-xl border border-white/10 bg-[#0a0c18]/85 p-1 opacity-100 backdrop-blur transition sm:opacity-0 sm:group-hover:opacity-100 focus-within:opacity-100">
            <span className="px-1.5 text-[11px] font-medium tabular-nums text-white/60">{Math.round(zoom * 100)}%</span>
            <InfoTip label="Zoom out" side="bottom">
              <Button variant="ghost" size="icon" className="h-11 w-11" aria-label="Zoom out" onClick={() => changeZoom(zoom - 0.25)} disabled={zoom <= MIN_ZOOM}>
                <ZoomOut className="h-4 w-4" />
              </Button>
            </InfoTip>
            <InfoTip label="Zoom in" side="bottom">
              <Button variant="ghost" size="icon" className="h-11 w-11" aria-label="Zoom in" onClick={() => changeZoom(zoom + 0.25)} disabled={zoom >= MAX_ZOOM}>
                <ZoomIn className="h-4 w-4" />
              </Button>
            </InfoTip>
            <InfoTip label="Reset view" side="bottom">
              <Button variant="ghost" size="icon" className="h-11 w-11" aria-label="Reset view" onClick={resetView} disabled={zoom === 1 && pan.x === 0 && pan.y === 0}>
                <RotateCcw className="h-4 w-4" />
              </Button>
            </InfoTip>
            <InfoTip label={isFullscreen ? "Exit fullscreen" : "Fullscreen"} side="bottom">
              <Button variant="ghost" size="icon" className="h-11 w-11" aria-label={isFullscreen ? "Exit fullscreen" : "Fullscreen"} onClick={toggleFullscreen}>
                {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
              </Button>
            </InfoTip>
          </div>

          {usePan && (
            <div className="pointer-events-none absolute bottom-3 left-3 z-20 flex items-center gap-1.5 rounded-full border border-white/10 bg-[#0a0c18]/85 px-2.5 py-1 text-[11px] text-white/60 backdrop-blur">
              <Hand className="h-3 w-3" /> Pan mode — scroll or drag to move
            </div>
          )}

          {children}
        </div>
        </div>
      </div>
    </TooltipProvider>
  );
}
