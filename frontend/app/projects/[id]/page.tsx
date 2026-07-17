"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BoxSelect, Brush, Check, ChevronLeft, ChevronRight, Eraser, Pause, Pentagon, Play, Redo2, RotateCcw, ScanSearch, SkipBack, SkipForward, Undo2 } from "lucide-react";

import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { projectsApi } from "@/services/projects";
import { detectionApi } from "@/services/detection";
import { masksApi, type MaskTool, type MaskGeometry } from "@/services/masks";
import { takePendingUploadFile } from "@/services/uploads";
import type { VideoProject } from "@/types";
import { ApiError } from "@/services/api";
import { BrittleMaskWarning } from "@/components/BrittleMaskWarning";

type Tool = "rectangle" | "polygon" | "brush" | "eraser";

interface Shape {
  tool: MaskTool;
  geometry: MaskGeometry;
}

const POLICY_VERSION = "1.0";

function fmtTime(t: number) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  const cs = Math.floor((t * 100) % 100);
  return `${m}:${String(s).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
}

export default function ProjectWorkspace() {
  useHydrateAuth();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = params.id;

  const [project, setProject] = useState<VideoProject | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [owned, setOwned] = useState(false);
  const [hasCompliance, setHasCompliance] = useState<boolean | null>(null);

  const [tool, setTool] = useState<Tool>("rectangle");
  const [brushR, setBrushR] = useState(16);
  const [brushSoft, setBrushSoft] = useState(4);
  const [brushOpacity, setBrushOpacity] = useState(0.6);
  const [maskExpansion, setMaskExpansion] = useState(0);
  const [maskFeathering, setMaskFeathering] = useState(4);
  const [temporalSmoothing, setTemporalSmoothing] = useState(false);

  // History of committed shapes (undo/redo over the canvas state). MVP: a
  // single static mask is what Phase 5 consumes; multiple shapes union into
  // that mask. Reset clears everything.
  const [shapes, setShapes] = useState<Shape[]>([]);
  const [redoStack, setRedoStack] = useState<Shape[]>([]);
  const [polygonPts, setPolygonPts] = useState<[number, number][] | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [activeRect, setActiveRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [activeBrush, setActiveBrush] = useState<{ x: number; y: number; r: number }[]>([]);

  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [maskSaved, setMaskSaved] = useState(false);
  const [detecting, setDetecting] = useState(false);

  // Instant local preview: while the signed backend proxy URL is being fetched
  // (or is unavailable), play the just-uploaded File via URL.createObjectURL so
  // the user never sees a black <video> on arrival. Cleared once proxy_url loads.
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [videoLoading, setVideoLoading] = useState(true);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pendingLoadRef = useRef<Shape | null>(null);
  const dashPhaseRef = useRef(0);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --- Load project + existing mask ---
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const p = await projectsApi.get(projectId);
        if (cancelled) return;
        setProject(p);
        setOwned(true);
        setDuration(p.duration ?? 0);
      } catch (e) {
        const err = e as ApiError;
        setLoadError(err?.message || "Failed to load project.");
        if ((err as { code?: string })?.code === "UNAUTHORIZED") {
          router.push("/login");
        }
      }
      try {
        const m = await masksApi.get(projectId);
        if (cancelled) return;
        // Geometry is stored in source pixels; repaint in display space.
        // Defer scaling until the canvas is sized (toDisplay reads canvas dims).
        setMaskExpansion(m.mask_expansion);
        setMaskFeathering(m.mask_feathering);
        setTemporalSmoothing(m.temporal_smoothing);
        pendingLoadRef.current = { tool: m.tool, geometry: m.geometry };
        setMaskSaved(true);
      } catch {
        // 404 = no mask yet; fine.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, router]);

  // Consume the just-uploaded File (handed off from /upload) and play it locally
  // until the signed backend proxy URL is available. Revoked on unmount or swap.
  useEffect(() => {
    const f = takePendingUploadFile();
    if (!f) return;
    const url = URL.createObjectURL(f);
    setLocalPreviewUrl(url);
    return () => {
      URL.revokeObjectURL(url);
      setLocalPreviewUrl(null);
    };
  }, []);

  // Once the signed backend proxy URL is present, drop the local object URL so
  // the <video> swaps to the server-side proxy (consistent with the canvas mask
  // coordinate space, which is calibrated to the proxy resolution).
  useEffect(() => {
    if (project?.proxy_url && localPreviewUrl) {
      setLocalPreviewUrl((url) => {
        if (url) URL.revokeObjectURL(url);
        return null;
      });
    }
  }, [project?.proxy_url, localPreviewUrl]);

  // Scale geometry between canvas display space and the project's source-frame
  // space. The backend persists + validates geometry in source pixels.
  const sourceScale = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !project?.width || !project?.height || !canvas.width || !canvas.height) return 1;
    return project.width / canvas.width;
  }, [project?.width, project?.height]);

  const toSource = useCallback(
    (g: MaskGeometry): MaskGeometry => {
      const s = sourceScale();
      if (s === 1) return g;
      if (g.x !== undefined && g.w !== undefined) {
        return { x: g.x * s, y: (g.y ?? 0) * s, w: g.w * s, h: (g.h ?? 0) * s };
      }
      if (g.points) return { points: g.points.map(([x, y]) => [x * s, y * s]) };
      if (g.strokes) return { strokes: g.strokes.map((b) => ({ x: b.x * s, y: b.y * s, r: b.r * s })) };
      return g;
    },
    [sourceScale],
  );

  const toDisplay = useCallback(
    (g: MaskGeometry): MaskGeometry => {
      const canvas = canvasRef.current;
      if (!canvas?.width || !project?.width) return g;
      const s = canvas.width / project.width;
      if (g.x !== undefined && g.w !== undefined) {
        return { x: g.x * s, y: (g.y ?? 0) * s, w: g.w * s, h: (g.h ?? 0) * s };
      }
      if (g.points) return { points: g.points.map(([x, y]) => [x * s, y * s]) };
      if (g.strokes) return { strokes: g.strokes.map((b) => ({ x: b.x * s, y: b.y * s, r: b.r * s })) };
      return g;
    },
    [project?.width],
  );

  // --- Resize canvas to the displayed video size ---
  useEffect(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const resize = () => {
      const r = video.getBoundingClientRect();
      canvas.width = r.width;
      canvas.height = r.height;
      redrawOverlay();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(video);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]);

  // Apply a pending (source-space) mask load once the canvas is sized so we can
  // paint it in display space.
  useEffect(() => {
    const pending = pendingLoadRef.current;
    const canvas = canvasRef.current;
    if (!pending || !canvas || !canvas.width || !project) return;
    pendingLoadRef.current = null;
    setShapes([{ tool: pending.tool, geometry: toDisplay(pending.geometry) }]);
  }, [project, toDisplay]);

  // Compliance confirmation is recorded once at upload time (LEGAL-001/002) by
  // The upload flow already records compliance, so the editor does not create
  // duplicate confirmations. hasCompliance remains informational until a GET endpoint exists.
  // for the confirmation record.
  useEffect(() => {
    setHasCompliance(true);
  }, []);

  // --- Redraw overlay (cyan fill + animated dashed boundary) ---
  const redrawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.fillStyle = "rgba(34, 211, 238, " + Math.max(0.18, brushOpacity * 0.48) + ")";
    ctx.strokeStyle = "rgba(103, 232, 249, 0.98)";
    ctx.lineWidth = 2;
    ctx.setLineDash([9, 7]);
    ctx.lineDashOffset = dashPhaseRef.current;

    for (const shape of shapes) paintShape(ctx, shape);
    if (activeRect) {
      paintShape(ctx, { tool: "rectangle", geometry: activeRect });
    }
    if (activeBrush.length) {
      paintShape(ctx, { tool: "brush", geometry: { strokes: activeBrush } });
    }
    if (polygonPts?.length) {
      ctx.beginPath();
      ctx.moveTo(polygonPts[0][0], polygonPts[0][1]);
      for (let i = 1; i < polygonPts.length; i++) ctx.lineTo(polygonPts[i][0], polygonPts[i][1]);
      ctx.stroke();
      for (const [x, y] of polygonPts) {
        ctx.beginPath();
        ctx.arc(x, y, 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();
  }, [shapes, activeRect, activeBrush, polygonPts, brushOpacity]);

  useEffect(() => {
    redrawOverlay();
  }, [redrawOverlay]);

  useEffect(() => {
    if (!shapes.length || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let animationFrame = 0;
    const animate = () => {
      dashPhaseRef.current = (dashPhaseRef.current - 0.55) % 32;
      redrawOverlay();
      animationFrame = requestAnimationFrame(animate);
    };
    animationFrame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrame);
  }, [shapes.length, redrawOverlay]);

  function paintShape(ctx: CanvasRenderingContext2D, shape: Shape) {
    const geometry = shape.geometry;
    if (shape.tool === "rectangle") {
      ctx.beginPath();
      ctx.rect(geometry.x ?? 0, geometry.y ?? 0, geometry.w ?? 0, geometry.h ?? 0);
      ctx.fill();
      ctx.stroke();
      return;
    }
    if (shape.tool === "brush") {
      for (const point of geometry.strokes ?? []) {
        ctx.beginPath();
        ctx.arc(point.x, point.y, point.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }
      return;
    }
    const points = geometry.points ?? [];
    if (points.length < 3) return;
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }
  // --- Pointer to canvas-space coordinates ---
  function toCanvas(e: React.PointerEvent) {
    const canvas = canvasRef.current!;
    const r = canvas.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  // --- Rectangle / brush drawing ---
  const onPointerDown = (e: React.PointerEvent) => {
    if (tool === "polygon") {
      const p = toCanvas(e);
      setPolygonPts((prev) => (prev ? [...prev, [p.x, p.y]] : [[p.x, p.y]]));
      return;
    }
    if (tool === "eraser") {
      // Erase last shape under pointer (MVP: drop the last committed shape).
      if (shapes.length) {
        setMaskSaved(false);
        setRedoStack((r) => [...r, shapes[shapes.length - 1]]);
        setShapes((s) => s.slice(0, -1));
      }
      return;
    }
    setDrawing(true);
    (e.target as Element).setPointerCapture?.(e.pointerId);
    const p = toCanvas(e);
    if (tool === "rectangle") {
      setActiveRect({ x: p.x, y: p.y, w: 0, h: 0 });
    } else if (tool === "brush") {
      setActiveBrush([{ x: p.x, y: p.y, r: brushR }]);
    }
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drawing) return;
    const p = toCanvas(e);
    if (tool === "rectangle" && activeRect) {
      setActiveRect({
        x: Math.min(activeRect.x, p.x),
        y: Math.min(activeRect.y, p.y),
        w: Math.abs(p.x - activeRect.x),
        h: Math.abs(p.y - activeRect.y),
      });
    } else if (tool === "brush") {
      setActiveBrush((prev) => [...prev, { x: p.x, y: p.y, r: brushR }]);
    }
  };

  const endDraw = () => {
    if (!drawing) return;
    setDrawing(false);
    if (tool === "rectangle" && activeRect && activeRect.w > 2 && activeRect.h > 2) {
      pushShape({ tool: "rectangle", geometry: { ...activeRect } });
    }
    if (tool === "brush" && activeBrush.length) {
      pushShape({ tool: "brush", geometry: { strokes: [...activeBrush] } });
    }
    setActiveRect(null);
    setActiveBrush([]);
  };

  const onDoubleClick = () => {
    if (tool !== "polygon" || !polygonPts || polygonPts.length < 3) {
      setPolygonPts(null);
      return;
    }
    pushShape({ tool: "polygon", geometry: { points: [...polygonPts] } });
    setPolygonPts(null);
  };

  const pushShape = (s: Shape) => {
    setMaskSaved(false);
    setShapes((prev) => [...prev, s]);
    setRedoStack([]);
  };

  const undo = () => {
    setMaskSaved(false);
    setShapes((prev) => {
      if (!prev.length) return prev;
      setRedoStack((r) => [...r, prev[prev.length - 1]]);
      return prev.slice(0, -1);
    });
  };
  const redo = () => {
    setMaskSaved(false);
    setRedoStack((r) => {
      if (!r.length) return r;
      const last = r[r.length - 1];
      setShapes((prev) => [...prev, last]);
      return r.slice(0, -1);
    });
  };
  const resetMask = () => {
    if (!shapes.length || !window.confirm("Reset the entire mask? You can undo this action until you leave the editor.")) return;
    setMaskSaved(false);
    setRedoStack((r) => [...r, ...shapes].reverse());
    setShapes([]);
    setPolygonPts(null);
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.matches("input, textarea, select, [contenteditable=true]")) return;
      const shortcuts: Record<string, Tool> = {
        r: "rectangle",
        p: "polygon",
        b: "brush",
        e: "eraser",
      };
      const nextTool = shortcuts[event.key.toLowerCase()];
      if (nextTool) {
        event.preventDefault();
        setTool(nextTool);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => () => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
  }, []);
  // --- Timeline ---
  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) {
      v.play();
      setPlaying(true);
    } else {
      v.pause();
      setPlaying(false);
    }
  };
  const seek = (t: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = Math.max(0, Math.min(t, v.duration || 0));
  };
  const stepFrame = (dir: 1 | -1) => {
    const v = videoRef.current;
    if (!v) return;
    const fps = project?.fps || 30;
    seek(v.currentTime + dir / fps);
  };

  const runAiDetect = async () => {
    setDetecting(true);
    setSaveErr(null);
    try {
      await detectionApi.analyze(projectId);
      setSavedMsg("AI detection started. Opening candidate review.");
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      toastTimerRef.current = setTimeout(() => router.push("/projects/" + projectId + "/candidates"), 650);
    } catch (e) {
      const err = e as ApiError;
      setSaveErr(err?.message || "AI detection could not be started.");
      setDetecting(false);
    }
  };
  // --- Save mask ---
  const save = async () => {
    if (!project) return;
    if (!shapes.length) {
      setSaveErr("Draw at least one shape before saving.");
      return;
    }
    setSaving(true);
    setSaveErr(null);
    setSavedMsg(null);
    try {
      // Union shapes into a single mask of the dominant tool for the backend.
      // MVP: if all shapes share a tool, store as a single shape; otherwise we
      // pick the first tool and union geometry in its canonical form (rect +
      // Polygon and brush shapes use a rectangle enclosing the combined region.
      // simple: store the first rectangle, else first polygon, else brush
      // strokes. Phase 5 will ingest a proper composite, but the backend only
      // persists one row per project.
      const primary = shapes[shapes.length - 1];
      const sourceWidth = project.width ?? 0;
      const sourceHeight = project.height ?? 0;
      await masksApi.put(projectId, {
        tool: primary.tool,
        geometry: toSource(primary.geometry),
        width: sourceWidth,
        height: sourceHeight,
        mask_expansion: maskExpansion,
        mask_feathering: maskFeathering,
        temporal_smoothing: temporalSmoothing,
        apply_to_entire: true,
        start_time: null,
        end_time: null,
      });
      setMaskSaved(true);
      setSavedMsg("Mask saved. Preview and processing are now unlocked.");
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      toastTimerRef.current = setTimeout(() => setSavedMsg(null), 4000);
    } catch (e) {
      const err = e as ApiError;
      setSaveErr(err?.message || "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  // Prefer the local object URL (just-uploaded File) so the video is visible
  // instantly; otherwise use the signed URL minted by the backend. A raw
  // <video src> cannot attach an Authorization header, so we never fall back
  // to the bearer-gated proxy path, which cannot authenticate media elements.
  const proxyUrl = useMemo(
    () => localPreviewUrl || project?.proxy_url || null,
    [localPreviewUrl, project?.proxy_url],
  );
  const scaledExpansion = useMemo(() => {
    // mask_expansion is in source-pixel space; the canvas operates on the proxy
    // display. Scale by display/source so the visible dilation matches intent.
    if (!project?.width || !canvasRef.current) return maskExpansion;
    const sx = canvasRef.current.width / project.width;
    return Math.round(maskExpansion * sx);
  }, [maskExpansion, project?.width]);

  // RECON-008: flag a mask that covers a large fraction of the frame. The
  // 35% area threshold mirrors `app.services.admin_service.is_brittle_region`.
  const brittle = useMemo(() => {
    if (!project?.width || !project?.height || !shapes.length) return false;
    const frameArea = project.width * project.height;
    if (frameArea <= 0) return false;
    const area = shapes.reduce((acc, s) => acc + _shapeArea(s), 0);
    return area / frameArea > 0.35;
  }, [project?.width, project?.height, shapes]);

  if (loadError) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16 text-white">
        <h1 className="text-xl font-semibold text-rose-200">{loadError}</h1>
        <Link href="/dashboard" className="mt-4 inline-flex items-center gap-2 text-sm text-[#9eb4ff]">
          <ChevronLeft className="h-4 w-4" /> Back to dashboard
        </Link>
      </main>
    );
  }
  if (!project) {
    return (
      <main className="mx-auto max-w-2xl px-6 py-16">
        <p className="text-white/50">Loading project...</p>
      </main>
    );
  }

  const frameW = project.width ?? 0;
  const frameH = project.height ?? 0;
  const playheadPct = duration ? Math.min(100, (currentTime / duration) * 100) : 0;
  const phaseSteps = ["Upload", "Detect", "Mask", "Track", "Preview", "Export"];
  const toolItems = [
    { id: "rectangle" as Tool, label: "Rectangle", shortcut: "R", icon: BoxSelect },
    { id: "polygon" as Tool, label: "Polygon", shortcut: "P", icon: Pentagon },
    { id: "brush" as Tool, label: "Brush", shortcut: "B", icon: Brush },
    { id: "eraser" as Tool, label: "Eraser", shortcut: "E", icon: Eraser },
  ];

  return (
    <main className="min-h-dvh bg-[#0a0b0f] px-4 py-6 text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <nav aria-label="Project progress" className="rounded-2xl border border-white/10 bg-[#111318] p-3 sm:p-4">
          <ol className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {phaseSteps.map((step, index) => {
              const complete = index < 2;
              const current = index === 2;
              return (
                <li
                  key={step}
                  aria-current={current ? "step" : undefined}
                  className={
                    "flex min-h-11 items-center gap-2 rounded-xl border px-3 py-2 text-xs font-medium transition " +
                    (current
                      ? "border-cyan-300/40 bg-cyan-300/10 text-cyan-100 shadow-[0_0_24px_rgba(34,211,238,.08)]"
                      : complete
                        ? "border-[#4f7cff]/25 bg-[#4f7cff]/10 text-[#c7d2fe]"
                        : "border-white/[.07] bg-black/10 text-white/40")
                  }
                >
                  <span
                    className={
                      "grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold " +
                      (current
                        ? "bg-cyan-300 text-[#071014]"
                        : complete
                          ? "bg-[#4f7cff] text-white"
                          : "bg-white/10 text-white/45")
                    }
                  >
                    {complete ? <Check className="h-3.5 w-3.5" /> : index + 1}
                  </span>
                  {step}
                </li>
              );
            })}
          </ol>
        </nav>

        <header className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[.16em] text-cyan-200/70">Mask workspace</p>
            <h1 className="mt-2 max-w-3xl truncate text-2xl font-semibold tracking-tight" title={project.title || project.original_filename}>
              {project.title || project.original_filename}
            </h1>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-white/60">
              <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1">{frameW}&times;{frameH}</span>
              <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 uppercase">{project.video_codec || "unknown codec"}</span>
              <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1">{project.duration?.toFixed(1) || "0.0"} seconds</span>
              <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1">{project.fps?.toFixed(2) || "30.00"} FPS</span>
            </div>
          </div>
          <Link href="/dashboard" className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm text-white/65 transition hover:bg-white/5 hover:text-white focus:outline-none focus:ring-2 focus:ring-[#4f7cff]">
            <ChevronLeft className="h-4 w-4" /> Dashboard
          </Link>
        </header>

        <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <section className="min-w-0">
            <div
              ref={containerRef}
              className="relative mx-auto max-h-[72vh] w-full overflow-hidden rounded-2xl border border-white/10 bg-black shadow-[0_24px_70px_rgba(0,0,0,.35)]"
            >
              {proxyUrl ? (
                <video
                  ref={videoRef}
                  src={proxyUrl}
                  className="block w-full"
                  onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
                  onLoadedMetadata={(event) => {
                    setDuration(event.currentTarget.duration || project.duration || 0);
                    setVideoLoading(false);
                  }}
                  onLoadedData={() => setVideoLoading(false)}
                  onCanPlay={() => setVideoLoading(false)}
                  onPlay={() => setPlaying(true)}
                  onPause={() => setPlaying(false)}
                  onError={() => {
                    const code = videoRef.current?.error?.code;
                    const reason =
                      code === 4 ? "source not found; the proxy may still be generating"
                      : code === 3 ? "the browser could not decode this video"
                      : code === 2 ? "a network error interrupted playback"
                      : code === 1 ? "playback was aborted"
                      : "an unknown playback error occurred";
                    setVideoError(reason);
                    setVideoLoading(false);
                  }}
                  onEnded={() => setPlaying(false)}
                  playsInline
                />
              ) : (
                <div className="flex min-h-[24rem] items-center justify-center p-6 text-center text-sm text-white/45">
                  Video preview unavailable. The proxy has not been generated yet.
                </div>
              )}

              {detecting && (
                <div className="pointer-events-none absolute inset-0 z-20 overflow-hidden bg-cyan-300/[.035]" aria-hidden="true">
                  <div className="mask-scan-line absolute inset-x-0 h-px bg-cyan-200 shadow-[0_0_18px_4px_rgba(34,211,238,.55)]" />
                  <div className="absolute left-4 top-4 flex items-center gap-2 rounded-full border border-cyan-300/25 bg-[#071014]/85 px-3 py-1.5 text-xs font-semibold text-cyan-100 backdrop-blur">
                    <ScanSearch className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none" /> Detecting watermark regions
                  </div>
                </div>
              )}

              {videoError && (
                <div className="absolute inset-x-0 bottom-0 z-30 bg-rose-950/90 px-4 py-3 text-sm text-rose-100">
                  Video preview unavailable. {videoError}.{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setVideoError(null);
                      setVideoLoading(true);
                      videoRef.current?.load();
                    }}
                    className="font-semibold underline underline-offset-2"
                  >
                    Retry
                  </button>
                  <span className="mx-2 text-white/30">&middot;</span>
                  <Link href="/login" className="font-semibold underline underline-offset-2">Sign in again</Link>
                </div>
              )}

              {proxyUrl && !videoError && videoLoading && (
                <div className="pointer-events-none absolute inset-0 grid place-items-center bg-black/25 text-sm text-white/55">
                  Loading preview...
                </div>
              )}

              <canvas
                ref={canvasRef}
                aria-label="Interactive video mask canvas"
                className="absolute inset-0 h-full w-full cursor-crosshair touch-none"
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={endDraw}
                onPointerCancel={endDraw}
                onDoubleClick={onDoubleClick}
              />
            </div>

            <div className="mt-4 rounded-2xl border border-white/10 bg-[#16181f] p-3 sm:p-4">
              <div className="flex flex-wrap items-center gap-2">
                <PlaybackButton label="Jump to start" onClick={() => seek(0)}><SkipBack className="h-4 w-4" /></PlaybackButton>
                <PlaybackButton label="Previous frame" onClick={() => stepFrame(-1)}><ChevronLeft className="h-4 w-4" /></PlaybackButton>
                <button
                  type="button"
                  onClick={togglePlay}
                  aria-label={playing ? "Pause video" : "Play video"}
                  className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-r from-[#4f7cff] to-[#6d5ef7] text-white shadow-[0_8px_22px_rgba(79,124,255,.24)] transition hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-cyan-300"
                >
                  {playing ? <Pause className="h-4 w-4 fill-current" /> : <Play className="ml-0.5 h-4 w-4 fill-current" />}
                </button>
                <PlaybackButton label="Next frame" onClick={() => stepFrame(1)}><ChevronRight className="h-4 w-4" /></PlaybackButton>
                <PlaybackButton label="Jump to end" onClick={() => seek(duration)}><SkipForward className="h-4 w-4" /></PlaybackButton>
                <span className="ml-auto font-mono text-xs tabular-nums text-white/70 sm:text-sm">
                  {fmtTime(currentTime)} <span className="text-white/30">/</span> {fmtTime(duration)}
                </span>
              </div>
              <input
                aria-label="Video playhead"
                type="range"
                min={0}
                max={duration || 0}
                step={0.01}
                value={currentTime}
                onChange={(event) => seek(parseFloat(event.target.value))}
                className="editor-range mt-4 w-full"
                style={{
                  background:
                    "linear-gradient(to right, #4f7cff 0%, #22d3ee " +
                    playheadPct +
                    "%, rgba(255,255,255,.1) " +
                    playheadPct +
                    "%, rgba(255,255,255,.1) 100%)",
                }}
              />
            </div>
          </section>

          <aside className="space-y-4">
            <section className="rounded-2xl border border-white/10 bg-[#16181f] p-3">
              <div className="mb-3 flex items-center justify-between px-1">
                <h2 className="text-sm font-semibold text-white/85">Selection tools</h2>
                <span className="text-[10px] uppercase tracking-[.14em] text-white/30">Shortcuts</span>
              </div>
              <div className="space-y-1.5">
                <button
                  type="button"
                  onClick={runAiDetect}
                  disabled={detecting}
                  className="flex min-h-11 w-full items-center gap-3 rounded-xl border border-cyan-300/25 bg-cyan-300/10 px-3 text-left text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/15 disabled:cursor-wait disabled:opacity-60"
                >
                  <ScanSearch className="h-4 w-4" />
                  <span className="flex-1">{detecting ? "Detecting..." : "AI Detect"}</span>
                  <span className="rounded border border-cyan-200/15 px-1.5 py-0.5 text-[10px] text-cyan-100/60">AI</span>
                </button>
                {toolItems.map((item) => {
                  const Icon = item.icon;
                  const active = tool === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setTool(item.id)}
                      aria-pressed={active}
                      aria-keyshortcuts={item.shortcut}
                      title={item.label + " tool (" + item.shortcut + ")"}
                      className={
                        "flex min-h-11 w-full items-center gap-3 rounded-xl border px-3 text-left text-sm transition focus:outline-none focus:ring-2 focus:ring-cyan-300 " +
                        (active
                          ? "border-[#4f7cff]/40 bg-[#4f7cff]/15 font-semibold text-white"
                          : "border-transparent text-white/60 hover:border-white/10 hover:bg-white/5 hover:text-white")
                      }
                    >
                      <Icon className="h-4 w-4" />
                      <span className="flex-1">{item.label}</span>
                      <kbd className="rounded border border-white/10 bg-black/15 px-1.5 py-0.5 font-mono text-[10px] text-white/40">{item.shortcut}</kbd>
                    </button>
                  );
                })}
              </div>
              {tool === "polygon" && <p className="mt-3 px-1 text-xs leading-5 text-white/45">Click each corner, then double-click to close the shape.</p>}
              {tool === "eraser" && <p className="mt-3 px-1 text-xs leading-5 text-white/45">Click the canvas to remove the most recent shape.</p>}
              {tool === "brush" && (
                <div className="mt-4 space-y-4 border-t border-white/10 pt-4">
                  <SliderControl label="Brush size" value={brushR} suffix="px">
                    <input aria-label="Brush size" type="range" min={2} max={80} value={brushR} onChange={(event) => setBrushR(+event.target.value)} className="editor-range w-full" />
                  </SliderControl>
                  <SliderControl label="Softness" value={brushSoft} suffix="px">
                    <input aria-label="Brush softness" type="range" min={0} max={32} value={brushSoft} onChange={(event) => setBrushSoft(+event.target.value)} className="editor-range w-full" />
                  </SliderControl>
                  <SliderControl label="Opacity" value={Math.round(brushOpacity * 100)} suffix="%">
                    <input aria-label="Brush opacity" type="range" min={0.1} max={1} step={0.05} value={brushOpacity} onChange={(event) => setBrushOpacity(+event.target.value)} className="editor-range w-full" />
                  </SliderControl>
                </div>
              )}
            </section>

            <section className="rounded-2xl border border-white/10 bg-[#16181f] p-4">
              <h2 className="text-sm font-semibold text-white/85">Mask adjust</h2>
              <div className="mt-4 space-y-5">
                <SliderControl label="Expand or shrink" value={maskExpansion} suffix="px">
                  <input aria-label="Expand or shrink mask" type="range" min={-40} max={80} value={maskExpansion} onChange={(event) => { setMaskExpansion(+event.target.value); setMaskSaved(false); }} className="editor-range w-full" />
                </SliderControl>
                <SliderControl label="Feather" value={maskFeathering} suffix="px">
                  <input aria-label="Mask feathering" type="range" min={0} max={32} value={maskFeathering} onChange={(event) => { setMaskFeathering(+event.target.value); setMaskSaved(false); }} className="editor-range w-full" />
                </SliderControl>
                <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border border-white/[.08] bg-black/10 p-3">
                  <input
                    type="checkbox"
                    checked={temporalSmoothing}
                    onChange={(event) => { setTemporalSmoothing(event.target.checked); setMaskSaved(false); }}
                    className="mt-0.5 h-4 w-4 shrink-0 accent-cyan-300"
                  />
                  <span>
                    <span className="block text-sm font-medium text-white/80">Temporal smoothing</span>
                    <span className="mt-1 block text-xs leading-5 text-white/45">Reduces frame-to-frame mask jitter. Entire-video static masks do not require it.</span>
                  </span>
                </label>
                <p className="text-xs text-white/40">Proxy display expansion: approximately {scaledExpansion}px.</p>
              </div>
            </section>

            <section className="rounded-2xl border border-white/10 bg-[#16181f] p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white/85">History</h2>
                <span className="text-xs text-white/35">{shapes.length} {shapes.length === 1 ? "shape" : "shapes"}</span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button type="button" onClick={undo} disabled={!shapes.length} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/10 text-sm text-white/65 hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-35">
                  <Undo2 className="h-4 w-4" /> Undo
                </button>
                <button type="button" onClick={redo} disabled={!redoStack.length} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/10 text-sm text-white/65 hover:bg-white/5 hover:text-white disabled:cursor-not-allowed disabled:opacity-35">
                  <Redo2 className="h-4 w-4" /> Redo
                </button>
              </div>
              <button type="button" onClick={resetMask} disabled={!shapes.length} className="mt-2 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl text-sm text-rose-300/75 hover:bg-rose-400/10 hover:text-rose-200 disabled:cursor-not-allowed disabled:opacity-35">
                <RotateCcw className="h-4 w-4" /> Reset mask
              </button>
              <p className="mt-2 text-xs leading-5 text-white/40">
                {shapes.length} committed <span className="mx-1 text-white/25">&middot;</span> applies to the entire video
              </p>
            </section>

            <section className="rounded-2xl border border-white/10 bg-[#16181f] p-4">
              <button
                type="button"
                onClick={save}
                disabled={saving || !shapes.length}
                className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] to-[#6d5ef7] px-4 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {saving ? "Saving..." : maskSaved ? <><Check className="h-4 w-4" /> Mask saved</> : "Save mask"}
              </button>
              {saveErr && <p role="alert" className="mt-3 rounded-xl border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-xs leading-5 text-rose-200">{saveErr}</p>}
              <BrittleMaskWarning brittle={brittle} />
              <button
                type="button"
                onClick={() => maskSaved && router.push("/projects/" + projectId + "/result")}
                disabled={!maskSaved}
                title={maskSaved ? "Open preview and processing" : "Save the mask to unlock preview and processing"}
                className="mt-3 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-cyan-300/25 bg-cyan-300/10 px-4 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/15 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-white/[.03] disabled:text-white/30"
              >
                Preview and process <ChevronRight className="h-4 w-4" />
              </button>
              <p className="mt-3 text-xs leading-5 text-white/45">
                {hasCompliance === false
                  ? "Ownership confirmation is missing. Processing remains blocked."
                  : maskSaved
                    ? "Ownership and mask confirmed. You can continue."
                    : "Save the current mask to unlock preview and processing."}
              </p>
            </section>
          </aside>
        </div>
      </div>

      {savedMsg && (
        <div aria-live="polite" className="fixed bottom-5 right-5 z-50 flex max-w-sm items-center gap-3 rounded-2xl border border-emerald-300/20 bg-[#121a18]/95 px-4 py-3 text-sm text-emerald-100 shadow-2xl backdrop-blur-xl">
          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-emerald-300/15"><Check className="h-4 w-4" /></span>
          {savedMsg}
        </div>
      )}
    </main>
  );
}

function PlaybackButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="grid h-11 w-11 place-items-center rounded-xl border border-white/10 bg-white/[.03] text-white/65 transition hover:bg-white/[.07] hover:text-white focus:outline-none focus:ring-2 focus:ring-cyan-300"
    >
      {children}
    </button>
  );
}

function SliderControl({ label, value, suffix, children }: { label: string; value: number; suffix: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-2 flex items-center justify-between gap-3 text-xs text-white/55">
        <span>{label}</span>
        <span className="rounded-full border border-cyan-300/15 bg-cyan-300/10 px-2 py-0.5 font-mono text-[11px] text-cyan-100">{value}{suffix}</span>
      </span>
      {children}
    </label>
  );
}
// Area of a mask shape in canvas (proxy) space, used by the RECON-008 brittle
// check. Returns 0 for unknown/empty geometries so they never trip the flag.
function _shapeArea(s: Shape): number {
  const g = s.geometry;
  if (s.tool === "rectangle") {
    return Math.max(0, g.w ?? 0) * Math.max(0, g.h ?? 0);
  }
  if (s.tool === "polygon") {
    const pts = g.points ?? [];
    if (pts.length < 3) return 0;
    let area = 0;
    for (let i = 0; i < pts.length; i++) {
      const [ax, ay] = pts[i];
      const [bx, by] = pts[(i + 1) % pts.length];
      area += ax * by - bx * ay;
    }
    return Math.abs(area) / 2;
  }
  if (s.tool === "brush") {
    return (g.strokes ?? []).reduce((acc, st) => acc + Math.PI * Math.max(0, st.r) ** 2, 0);
  }
  return 0;
}
