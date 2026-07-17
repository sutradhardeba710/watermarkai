"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BoxSelect, CheckCircle2, LoaderCircle, ScanSearch } from "lucide-react";

import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { ApiError } from "@/services/api";
import { detectionApi } from "@/services/detection";
import { pollJob } from "@/services/process";
import { projectsApi } from "@/services/projects";
import type { VideoProject, WatermarkCandidate } from "@/types";

function fmtPct(value: number) {
  return Math.max(0, Math.min(100, Math.round(value))) + "%";
}

export default function CandidateReviewPage() {
  useHydrateAuth();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = params.id;
  const abortRef = useRef<AbortController | null>(null);

  const [project, setProject] = useState<VideoProject | null>(null);
  const [candidates, setCandidates] = useState<WatermarkCandidate[]>([]);
  const [notes, setNotes] = useState<string | null>(null);
  const [needsManual, setNeedsManual] = useState(false);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeProgress, setAnalyzeProgress] = useState(0);
  const [analyzeStage, setAnalyzeStage] = useState("Queued...");
  const [approvingId, setApprovingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadCandidates = useCallback(async () => {
    const response = await detectionApi.listCandidates(projectId);
    setCandidates(response.candidates);
    setNeedsManual(response.needs_manual_selection);
    setNotes(response.notes ?? null);
    return response.candidates;
  }, [projectId]);

  const runAnalysis = useCallback(async (rerun = false) => {
    setAnalyzing(true);
    setError(null);
    setApprovingId(null);
    if (rerun) {
      // A rerun deletes the previous candidate rows server-side. Clear their
      // cards immediately so an old ID cannot be approved while the worker
      // generates the replacement result.
      setCandidates([]);
      setNeedsManual(false);
      setNotes("Refreshing detection results...");
    }
    setAnalyzeProgress(0);
    setAnalyzeStage("Queued...");
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const queued = await detectionApi.analyze(projectId, rerun);
      const finished = await pollJob(
        queued.job_id,
        (status) => {
          setAnalyzeProgress(status.progress);
          setAnalyzeStage((status.current_stage || status.status).replace(/_/g, " "));
        },
        { signal: controller.signal },
      );
      if (finished.status !== "completed") {
        throw new Error(finished.error_message || "AI detection did not complete.");
      }
      await loadCandidates();
      setError(null);
      setAnalyzeProgress(100);
      setAnalyzeStage("Detection complete");
    } catch (reason) {
      if ((reason as Error)?.name !== "AbortError") {
        const apiError = reason as ApiError;
        setError(apiError?.message || "AI detection failed. You can draw the mask manually.");
      }
    } finally {
      setAnalyzing(false);
    }
  }, [loadCandidates, projectId]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const loadedProject = await projectsApi.get(projectId);
        if (cancelled) return;
        setProject(loadedProject);
        const existing = await loadCandidates();
        if (!cancelled && existing.length === 0) void runAnalysis(false);
      } catch (reason) {
        const apiError = reason as ApiError;
        if (!cancelled) setError(apiError?.message || "Unable to load detection results.");
        if ((apiError as { code?: string })?.code === "UNAUTHORIZED") router.push("/login");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [loadCandidates, projectId, router, runAnalysis]);

  const approve = useCallback(async (candidate: WatermarkCandidate) => {
    if (analyzing) return;
    setApprovingId(candidate.id);
    setError(null);
    try {
      await detectionApi.approve(candidate.id);
      router.push("/projects/" + projectId);
    } catch (reason) {
      const apiError = reason as ApiError;
      if ((apiError as { code?: string })?.code === "NOT_FOUND") {
        // A just-finished rerun may have replaced this candidate row.
        await loadCandidates();
        setError("Detection results were refreshed. Please choose the current candidate.");
      } else {
        setError(apiError?.message || "Unable to approve this mask.");
      }
      setApprovingId(null);
    }
  }, [analyzing, loadCandidates, projectId, router]);

  const title = project?.title || project?.original_filename || "Detection review";
  const sortedCandidates = useMemo(
    () => [...candidates].sort((a, b) => b.confidence - a.confidence),
    [candidates],
  );

  if (loading && !project) {
    return <main className="mx-auto max-w-5xl px-6 py-16"><p className="text-white/50">Loading project...</p></main>;
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-8 text-white">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[.18em] text-[#9eb4ff]">AI detection</p>
          <h1 className="mt-2 max-w-2xl truncate text-2xl font-bold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-white/50">
            {project?.width || "?"}&times;{project?.height || "?"}
            <span className="mx-2 text-white/25">&middot;</span>
            {project?.video_codec || "unknown codec"}
            <span className="mx-2 text-white/25">&middot;</span>
            {project?.duration?.toFixed(1) || "?"}s
          </p>
        </div>
        <Link href="/dashboard" className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white/60 transition hover:bg-white/5 hover:text-white">
          Back to dashboard
        </Link>
      </header>

      {analyzing && (
        <section className="mt-6 rounded-2xl border border-cyan-400/20 bg-cyan-400/[.06] p-5" aria-live="polite">
          <div className="flex items-center gap-3">
            <LoaderCircle className="h-5 w-5 animate-spin text-cyan-300 motion-reduce:animate-none" />
            <div className="flex-1">
              <p className="text-sm font-medium text-white/75">{analyzeStage || "Queued..."} {fmtPct(analyzeProgress)}</p>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full bg-gradient-to-r from-[#4f7cff] via-cyan-400 to-[#6d5ef7] transition-[width]" style={{ width: fmtPct(analyzeProgress) }} />
              </div>
            </div>
          </div>
        </section>
      )}

      {error && <p className="mt-6 rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</p>}

      {!analyzing && sortedCandidates.length === 0 ? (
        <section className="mt-8 rounded-2xl border border-white/10 bg-[#16181f] p-8 text-center">
          <ScanSearch className="mx-auto h-10 w-10 text-cyan-300" />
          <h2 className="mt-4 text-lg font-semibold">{needsManual ? "No reliable watermark found" : "No detection candidates yet"}</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-white/50">{notes || "Run AI detection again, or open the manual editor to draw an exact mask."}</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button onClick={() => void runAnalysis(true)} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] to-[#6d5ef7] px-5 py-2.5 text-sm font-semibold">
              <ScanSearch className="h-4 w-4" /> Run detection again
            </button>
            <Link href={"/projects/" + projectId} className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/10 px-5 py-2.5 text-sm font-medium text-white/70 hover:bg-white/5 hover:text-white">
              <BoxSelect className="h-4 w-4" /> Open manual mask editor
            </Link>
          </div>
        </section>
      ) : (
        <section className="mt-8">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">Select a detected mask</h2>
              <p className="mt-1 text-sm text-white/45">Review the highlighted region before approving it.</p>
            </div>
            {!analyzing && (
              <button onClick={() => void runAnalysis(true)} className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white/65 hover:bg-white/5 hover:text-white">
                Run again
              </button>
            )}
          </div>

          <div className="mt-5 grid gap-5 md:grid-cols-2">
            {sortedCandidates.map((candidate, index) => {
              const frameWidth = project?.width || 1;
              const frameHeight = project?.height || 1;
              const box = candidate.bounding_box;
              return (
                <article key={candidate.id} className="overflow-hidden rounded-2xl border border-white/10 bg-[#16181f] transition hover:border-cyan-300/30">
                  <div className="relative aspect-video overflow-hidden bg-gradient-to-br from-[#0f2032] to-[#171a35]">
                    {project?.thumbnail_url ? <img src={project.thumbnail_url} alt="" className="h-full w-full object-contain" /> : <ScanSearch className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 text-white/20" />}
                    <div
                      className="absolute border-2 border-dashed border-cyan-300 bg-cyan-300/20 shadow-[0_0_24px_rgba(34,211,238,.22)]"
                      style={{
                        left: Math.max(0, box.x / frameWidth * 100) + "%",
                        top: Math.max(0, box.y / frameHeight * 100) + "%",
                        width: Math.min(100, box.w / frameWidth * 100) + "%",
                        height: Math.min(100, box.h / frameHeight * 100) + "%",
                      }}
                    />
                    <span className="absolute left-3 top-3 rounded-full border border-cyan-300/20 bg-black/65 px-2.5 py-1 text-xs font-medium text-cyan-200">Candidate {index + 1}</span>
                  </div>
                  <div className="p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="font-semibold capitalize">{candidate.candidate_type.replace(/_/g, " ")}</h3>
                        <p className="mt-1 text-xs text-white/45">
                          {Math.round(box.w)}&times;{Math.round(box.h)} px
                          <span className="mx-2 text-white/25">&middot;</span>
                          {candidate.is_static ? "Static" : "Tracked"}
                        </p>
                      </div>
                      <span className="rounded-full bg-emerald-400/10 px-2.5 py-1 text-xs font-semibold text-emerald-300">{fmtPct((candidate.confidence / 5) * 100)} confidence</span>
                    </div>
                    <button
                      onClick={() => void approve(candidate)}
                      disabled={analyzing || approvingId !== null}
                      className="mt-5 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] to-[#6d5ef7] px-4 py-2.5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {approvingId === candidate.id ? <><LoaderCircle className="h-4 w-4 animate-spin motion-reduce:animate-none" /> Approving...</> : <><CheckCircle2 className="h-4 w-4" /> Approve mask</>}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}
    </main>
  );
}