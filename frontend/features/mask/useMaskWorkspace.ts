"use client";

import type React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { projectsApi } from "@/services/projects";
import { masksApi, type MaskTool, type MaskGeometry, type PersistedMaskTool } from "@/services/masks";
import { takePendingUploadFile } from "@/services/uploads";
import type { VideoProject } from "@/types";
import { ApiError } from "@/services/api";

export type Tool = "rectangle" | "polygon" | "brush" | "eraser" | "pan";

export interface Shape {
  tool: MaskTool;
  geometry: MaskGeometry;
}

export interface HistoryEntry {
  id: number;
  label: string;
  kind: "create" | "adjust" | "erase" | "reset" | "detect";
}

/** Editing lifecycle used to drive the honest SaveStatus indicator. */
export type SaveState = "clean" | "dirty" | "saving" | "saved" | "error";

/**
 * Owns the entire mask-editor domain. The canvas geometry math
 * (toSource/toDisplay/sourceScale/paintShape/redrawOverlay and the pointer
 * handlers) is preserved verbatim from the original single-file workspace — it
 * is calibrated to the proxy resolution and the backend validates source-pixel
 * geometry, so it must not be altered. Everything else (history log, richer
 * save state, read-only awareness) is additive and presentational.
 */
export function useMaskWorkspace(projectId: string) {
  const router = useRouter();

  const [project, setProject] = useState<VideoProject | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [tool, setToolState] = useState<Tool>("rectangle");
  const [brushR, setBrushR] = useState(16);
  const [brushSoft, setBrushSoft] = useState(4);
  const [brushOpacity, setBrushOpacity] = useState(0.6);
  const [maskExpansion, setMaskExpansion] = useState(0);
  const [maskFeathering, setMaskFeathering] = useState(4);
  const [temporalSmoothing, setTemporalSmoothing] = useState(false);

  const [shapes, setShapes] = useState<Shape[]>([]);
  const [redoStack, setRedoStack] = useState<Shape[]>([]);
  const [polygonPts, setPolygonPts] = useState<[number, number][] | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [activeRect, setActiveRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [activeBrush, setActiveBrush] = useState<{ x: number; y: number; r: number }[]>([]);

  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);

  const [saveState, setSaveState] = useState<SaveState>("clean");
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [maskSaved, setMaskSaved] = useState(false);

  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const historyIdRef = useRef(0);

  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [videoErrorCode, setVideoErrorCode] = useState<number | null>(null);
  const [videoLoading, setVideoLoading] = useState(true);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  // Saved mask waiting for the canvas to be sized. State (not a ref) so the
  // apply effect re-runs once the fetch completes — a ref write triggers no
  // render, which used to leave a reopened project's saved mask unpainted.
  const [pendingLoad, setPendingLoad] = useState<{ tool: PersistedMaskTool; geometry: MaskGeometry } | null>(null);
  const rectOriginRef = useRef<{ x: number; y: number } | null>(null);
  const dashPhaseRef = useRef(0);
  const savedOnceRef = useRef(false);

  // A project is read-only once expired/cancelled; editing is disabled but the
  // user can still review the saved state.
  const readOnly = useMemo(
    () => project?.status === "expired" || project?.status === "cancelled",
    [project?.status],
  );

  const pushHistory = useCallback((label: string, kind: HistoryEntry["kind"]) => {
    historyIdRef.current += 1;
    setHistory((prev) => [...prev, { id: historyIdRef.current, label, kind }]);
  }, []);

  // --- Load project + existing mask ---
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const p = await projectsApi.get(projectId);
        if (cancelled) return;
        setProject(p);
        setDuration(p.duration ?? 0);
      } catch (e) {
        const err = e as ApiError;
        setLoadError(err?.message || "Failed to load project.");
        if ((err as { code?: string })?.code === "UNAUTHORIZED") router.push("/login");
      }
      try {
        const m = await masksApi.get(projectId);
        if (cancelled) return;
        setMaskExpansion(m.mask_expansion);
        setMaskFeathering(m.mask_feathering);
        setTemporalSmoothing(m.temporal_smoothing);
        setPendingLoad({ tool: m.tool, geometry: m.geometry });
        setMaskSaved(true);
        savedOnceRef.current = true;
        setSaveState("saved");
      } catch {
        // 404 = no mask yet; fine.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, router]);

  // Consume the just-uploaded File and play it locally until the proxy is ready.
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

  useEffect(() => {
    if (project?.proxy_url && localPreviewUrl) {
      setLocalPreviewUrl((url) => {
        if (url) URL.revokeObjectURL(url);
        return null;
      });
    }
  }, [project?.proxy_url, localPreviewUrl]);

  // --- Geometry scaling (verbatim) ---
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

  /** Expand a persisted mask (simple or "multi" composite) into editor shapes. */
  const expandToShapes = useCallback(
    (tool: PersistedMaskTool, geometry: MaskGeometry): Shape[] => {
      if (tool === "multi") {
        return (geometry.shapes ?? []).map((sub) => ({ tool: sub.tool, geometry: toDisplay(sub.geometry) }));
      }
      return [{ tool, geometry: toDisplay(geometry) }];
    },
    [toDisplay],
  );

  // --- Resize canvas to the displayed video size (verbatim) ---
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

  // Apply a pending (source-space) mask once the canvas is sized. Retries on
  // animation frames because the canvas gets its size from a ResizeObserver,
  // which doesn't trigger a re-render this effect could key off.
  useEffect(() => {
    if (!pendingLoad || !project) return;
    let raf = 0;
    const tryApply = () => {
      const canvas = canvasRef.current;
      if (!canvas || !canvas.width) {
        raf = requestAnimationFrame(tryApply);
        return;
      }
      setPendingLoad(null);
      setShapes(expandToShapes(pendingLoad.tool, pendingLoad.geometry));
      pushHistory("Saved mask loaded", "detect");
    };
    tryApply();
    return () => cancelAnimationFrame(raf);
  }, [pendingLoad, project, expandToShapes, pushHistory]);

  // --- paintShape (verbatim) ---
  const paintShape = useCallback((ctx: CanvasRenderingContext2D, shape: Shape) => {
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
  }, []);

  // --- redrawOverlay (verbatim) ---
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
    if (activeRect) paintShape(ctx, { tool: "rectangle", geometry: activeRect });
    if (activeBrush.length) paintShape(ctx, { tool: "brush", geometry: { strokes: activeBrush } });
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
  }, [shapes, activeRect, activeBrush, polygonPts, brushOpacity, paintShape]);

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

  // --- Pointer to canvas-space (verbatim) ---
  function toCanvas(e: React.PointerEvent) {
    const canvas = canvasRef.current!;
    const r = canvas.getBoundingClientRect();
    // Account for any CSS zoom transform applied to the canvas wrapper so mask
    // coordinates stay in true canvas (proxy) space. Clamp to the canvas: with
    // pointer capture active a drag can leave the video, and unclamped coords
    // scale past the source frame, which the backend rejects with a 422.
    const scaleX = canvas.width / r.width;
    const scaleY = canvas.height / r.height;
    const x = (e.clientX - r.left) * scaleX;
    const y = (e.clientY - r.top) * scaleY;
    return {
      x: Math.min(Math.max(0, x), canvas.width),
      y: Math.min(Math.max(0, y), canvas.height),
    };
  }

  const markDirty = useCallback(() => {
    setMaskSaved(false);
    setSaveState("dirty");
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    if (readOnly || tool === "pan") return;
    if (tool === "polygon") {
      const p = toCanvas(e);
      setPolygonPts((prev) => (prev ? [...prev, [p.x, p.y]] : [[p.x, p.y]]));
      return;
    }
    if (tool === "eraser") {
      if (shapes.length) {
        markDirty();
        setRedoStack((r) => [...r, shapes[shapes.length - 1]]);
        setShapes((s) => s.slice(0, -1));
        pushHistory("Mask area erased", "erase");
      }
      return;
    }
    setDrawing(true);
    (e.target as Element).setPointerCapture?.(e.pointerId);
    const p = toCanvas(e);
    if (tool === "rectangle") {
      rectOriginRef.current = { x: p.x, y: p.y };
      setActiveRect({ x: p.x, y: p.y, w: 0, h: 0 });
    } else if (tool === "brush") setActiveBrush([{ x: p.x, y: p.y, r: brushR }]);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drawing) return;
    const p = toCanvas(e);
    if (tool === "rectangle" && activeRect) {
      // Measure against the fixed drag origin — using the previous rect state
      // makes the anchor drift when the pointer crosses back over it.
      const o = rectOriginRef.current ?? { x: activeRect.x, y: activeRect.y };
      setActiveRect({
        x: Math.min(o.x, p.x),
        y: Math.min(o.y, p.y),
        w: Math.abs(p.x - o.x),
        h: Math.abs(p.y - o.y),
      });
    } else if (tool === "brush") {
      setActiveBrush((prev) => [...prev, { x: p.x, y: p.y, r: brushR }]);
    }
  };

  const endDraw = () => {
    if (!drawing) return;
    setDrawing(false);
    rectOriginRef.current = null;
    if (tool === "rectangle" && activeRect && activeRect.w > 2 && activeRect.h > 2) {
      pushShape({ tool: "rectangle", geometry: { ...activeRect } });
      pushHistory("Rectangle created", "create");
    }
    if (tool === "brush" && activeBrush.length) {
      pushShape({ tool: "brush", geometry: { strokes: [...activeBrush] } });
      pushHistory("Brush stroke added", "create");
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
    pushHistory("Polygon created", "create");
    setPolygonPts(null);
  };

  const pushShape = (s: Shape) => {
    markDirty();
    setShapes((prev) => [...prev, s]);
    setRedoStack([]);
  };

  const cancelDrawing = useCallback(() => {
    setPolygonPts(null);
    setActiveRect(null);
    setActiveBrush([]);
    setDrawing(false);
  }, []);

  const undo = useCallback(() => {
    setShapes((prev) => {
      if (!prev.length) return prev;
      markDirty();
      setRedoStack((r) => [...r, prev[prev.length - 1]]);
      pushHistory("Undo", "adjust");
      return prev.slice(0, -1);
    });
  }, [markDirty, pushHistory]);

  const redo = useCallback(() => {
    setRedoStack((r) => {
      if (!r.length) return r;
      markDirty();
      const last = r[r.length - 1];
      setShapes((prev) => [...prev, last]);
      pushHistory("Redo", "adjust");
      return r.slice(0, -1);
    });
  }, [markDirty, pushHistory]);

  /** Reset now goes through a Dialog in the UI, so this performs the action. */
  const resetMask = useCallback(() => {
    if (!shapes.length) return;
    markDirty();
    setRedoStack((r) => [...r, ...shapes].reverse());
    setShapes([]);
    setPolygonPts(null);
    pushHistory("Mask reset", "reset");
  }, [shapes, markDirty, pushHistory]);

  // Adjust setters that log + mark dirty.
  const updateExpansion = useCallback((v: number) => {
    setMaskExpansion(v);
    markDirty();
    pushHistory(`Expand/shrink set to ${v}px`, "adjust");
  }, [markDirty, pushHistory]);

  const updateFeather = useCallback((v: number) => {
    setMaskFeathering(v);
    markDirty();
    pushHistory(`Feather set to ${v}px`, "adjust");
  }, [markDirty, pushHistory]);

  const updateTemporal = useCallback((v: boolean) => {
    setTemporalSmoothing(v);
    markDirty();
    pushHistory(`Temporal smoothing ${v ? "on" : "off"}`, "adjust");
  }, [markDirty, pushHistory]);

  const resetProperties = useCallback(() => {
    setMaskExpansion(0);
    setMaskFeathering(4);
    setTemporalSmoothing(false);
    markDirty();
    pushHistory("Adjustments reset to defaults", "adjust");
  }, [markDirty, pushHistory]);

  const setTool = useCallback(
    (t: Tool) => {
      if (readOnly && t !== "pan") return;
      setToolState(t);
    },
    [readOnly],
  );

  // --- Playback ---
  const togglePlay = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) {
      void v.play();
      setPlaying(true);
    } else {
      v.pause();
      setPlaying(false);
    }
  }, []);

  const seek = useCallback((t: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = Math.max(0, Math.min(t, v.duration || 0));
  }, []);

  const stepFrame = useCallback(
    (dir: 1 | -1) => {
      const v = videoRef.current;
      if (!v) return;
      const fps = project?.fps || 30;
      seek(v.currentTime + dir / fps);
    },
    [project?.fps, seek],
  );

  const toggleMute = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    v.muted = !v.muted;
    setMuted(v.muted);
  }, []);

  const changeRate = useCallback((rate: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.playbackRate = rate;
    setPlaybackRate(rate);
  }, []);

  // --- Save (verbatim persistence contract) ---
  const save = useCallback(async () => {
    if (!project || readOnly) return;
    if (!shapes.length) {
      setSaveErr("Create or accept a mask before saving.");
      setSaveState("error");
      return;
    }
    setSaveState("saving");
    setSaveErr(null);
    try {
      // Persist every drawn shape: one shape saves as itself; several save as
      // a "multi" composite (the editor renders them all, so saving only the
      // last one silently dropped regions from the processed mask).
      const sourceWidth = project.width ?? 0;
      const sourceHeight = project.height ?? 0;
      const payload =
        shapes.length === 1
          ? { tool: shapes[0].tool as PersistedMaskTool, geometry: toSource(shapes[0].geometry) }
          : {
              tool: "multi" as PersistedMaskTool,
              geometry: {
                shapes: shapes.map((s) => ({ tool: s.tool, geometry: toSource(s.geometry) })),
              },
            };
      await masksApi.put(projectId, {
        ...payload,
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
      savedOnceRef.current = true;
      setSaveState("saved");
      return true;
    } catch (e) {
      const err = e as ApiError;
      setSaveErr(err?.message || "We couldn't save your mask.");
      setSaveState("error");
      return false;
    }
  }, [project, readOnly, shapes, projectId, toSource, maskExpansion, maskFeathering, temporalSmoothing]);

  // Debounced re-persist AFTER the first successful save, so later tweaks to an
  // already-saved mask are kept without the user re-clicking Save. Before the
  // first save, the user saves explicitly (status stays "Unsaved changes").
  useEffect(() => {
    if (!savedOnceRef.current || saveState !== "dirty" || !shapes.length || readOnly) return;
    const t = setTimeout(() => {
      void save();
    }, 1200);
    return () => clearTimeout(t);
  }, [saveState, shapes, maskExpansion, maskFeathering, temporalSmoothing, readOnly, save]);

  const proxyUrl = useMemo(
    () => localPreviewUrl || project?.proxy_url || null,
    [localPreviewUrl, project?.proxy_url],
  );

  const scaledExpansion = useMemo(() => {
    if (!project?.width || !canvasRef.current) return maskExpansion;
    const sx = canvasRef.current.width / project.width;
    return Math.round(maskExpansion * sx);
  }, [maskExpansion, project?.width]);

  // RECON-008 brittle check (verbatim heuristic).
  const brittle = useMemo(() => {
    if (!project?.width || !project?.height || !shapes.length) return false;
    const frameArea = project.width * project.height;
    if (frameArea <= 0) return false;
    const area = shapes.reduce((acc, s) => acc + shapeArea(s), 0);
    return area / frameArea > 0.35;
  }, [project?.width, project?.height, shapes]);

  const hasMask = shapes.length > 0;

  // Accept an externally-loaded mask (from inline AI detection approval).
  const applyLoadedMask = useCallback(
    (m: { tool: PersistedMaskTool; geometry: MaskGeometry; mask_expansion: number; mask_feathering: number; temporal_smoothing: boolean }) => {
      setMaskExpansion(m.mask_expansion);
      setMaskFeathering(m.mask_feathering);
      setTemporalSmoothing(m.temporal_smoothing);
      setShapes(expandToShapes(m.tool, m.geometry));
      setRedoStack([]);
      setMaskSaved(true);
      savedOnceRef.current = true;
      setSaveState("saved");
      pushHistory("AI detection applied", "detect");
    },
    [expandToShapes, pushHistory],
  );

  return {
    // data
    project,
    loadError,
    readOnly,
    proxyUrl,
    duration,
    currentTime,
    playing,
    muted,
    playbackRate,
    // refs
    videoRef,
    canvasRef,
    containerRef,
    // tool state
    tool,
    setTool,
    brushR,
    setBrushR,
    brushSoft,
    setBrushSoft,
    brushOpacity,
    setBrushOpacity,
    // mask props
    maskExpansion,
    maskFeathering,
    temporalSmoothing,
    scaledExpansion,
    updateExpansion,
    updateFeather,
    updateTemporal,
    resetProperties,
    // shapes + history
    shapes,
    redoStack,
    hasMask,
    history,
    brittle,
    polygonPts,
    // actions
    onPointerDown,
    onPointerMove,
    endDraw,
    onDoubleClick,
    cancelDrawing,
    undo,
    redo,
    resetMask,
    // playback
    togglePlay,
    seek,
    stepFrame,
    toggleMute,
    changeRate,
    setCurrentTime,
    setDuration,
    setPlaying,
    // save
    save,
    saveState,
    saveErr,
    setSaveErr,
    maskSaved,
    applyLoadedMask,
    // video status
    videoError,
    setVideoError,
    videoErrorCode,
    setVideoErrorCode,
    videoLoading,
    setVideoLoading,
  };
}

/** Area of a mask shape in canvas (proxy) space for RECON-008 (verbatim). */
export function shapeArea(s: Shape): number {
  const g = s.geometry;
  if (s.tool === "rectangle") return Math.max(0, g.w ?? 0) * Math.max(0, g.h ?? 0);
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
