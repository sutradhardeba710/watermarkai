"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Download,
  Film,
  Gauge,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { ReactCompareSlider, ReactCompareSliderHandle } from "react-compare-slider";
import { toast } from "sonner";

import { AppShell } from "@/components/AppShell";
import { WorkflowStepper } from "@/components/WorkflowStepper";
import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { ApiError } from "@/services/api";
import { downloadApi, pollJob, previewApi, processApi } from "@/services/process";
import { projectsApi } from "@/services/projects";
import type { JobStatus, PreviewResponse, VideoProject } from "@/types";

const DURATIONS: Array<3 | 5 | 10> = [3, 5, 10];

export default function PreviewApproveScreen() {
  useHydrateAuth();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = params.id;

  const [project, setProject] = useState<VideoProject | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [building, setBuilding] = useState(false);
  const [buildProgress, setBuildProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [duration, setDuration] = useState<3 | 5 | 10>(5);
  const [start, setStart] = useState(0);
  const [loop, setLoop] = useState(true);
  const [approving, setApproving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [downloading, setDownloading] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const beforeVideoRef = useRef<HTMLVideoElement | null>(null);
  const afterVideoRef = useRef<HTMLVideoElement | null>(null);
  const approveButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const loaded = await projectsApi.get(projectId);
        if (cancelled) return;
        setProject(loaded);
        if (loaded.preview_storage_key) {
          setPreview({ ...emptyPreview(), artifact_storage_key: loaded.preview_storage_key });
        }
      } catch (reason) {
        const apiError = reason as ApiError;
        setError(apiError?.message || "Failed to load project.");
        if ((apiError as { code?: string })?.code === "UNAUTHORIZED") router.push("/login");
      }
    })();
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [projectId, router]);

  useEffect(() => {
    if (!building) return;
    setBuildProgress(8);
    const timer = window.setInterval(() => {
      setBuildProgress((current) => current < 72 ? current + 7 : Math.min(92, current + 2));
    }, 700);
    return () => window.clearInterval(timer);
  }, [building]);

  useEffect(() => {
    if (!confirming) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setConfirming(false);
        approveButtonRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [confirming]);

  const buildPreview = useCallback(async () => {
    if (!project || building) return;
    setBuilding(true);
    setError(null);
    try {
      const response = await previewApi.create(projectId, {
        start_seconds: start,
        duration_seconds: duration,
      });
      setPreview(response);
      const refreshed = await projectsApi.get(projectId);
      setProject(refreshed);
      setBuildProgress(100);
      toast.success("Preview ready. Drag the handle to compare frames.");
    } catch (reason) {
      const apiError = reason as ApiError;
      setError(apiError?.message || "Preview build failed. Check the mask and try again.");
      toast.error("Preview could not be built.");
    } finally {
      setBuilding(false);
    }
  }, [building, duration, project, projectId, start]);

  const watchJob = useCallback(async (jobId: string) => {
    const controller = new AbortController();
    abortRef.current = controller;
    const finished = await pollJob(jobId, setJob, {
      signal: controller.signal,
      intervalMs: 1500,
    });
    if (finished.status !== "completed") {
      throw new Error(finished.error_message || `Processing ended: ${finished.status}`);
    }
    const refreshed = await projectsApi.get(projectId);
    setProject(refreshed);
    toast.success(`${refreshed.original_filename || "Your video"} is ready to download.`);
  }, [projectId]);

  const beginProcessing = useCallback(async () => {
    if (!project || approving) return;
    setConfirming(false);
    setApproving(true);
    setError(null);
    try {
      // Start the job FIRST — only claim success once the backend accepted it
      // (a 402 INSUFFICIENT_CREDITS here must not show a fake processing screen).
      const response = await processApi.start(projectId);
      router.replace(`/projects/${projectId}/result?processing=1`, { scroll: false });
      toast.message("Full-resolution processing started.");
      await watchJob(response.job_id);
    } catch (reason) {
      if ((reason as Error)?.name !== "AbortError") {
        const apiError = reason as ApiError;
        const code = (apiError as { code?: string })?.code;
        const message = code === "INSUFFICIENT_CREDITS"
          ? (apiError?.message || "Not enough credits.") + " Upgrade your plan or wait for the daily reset."
          : apiError?.message || "Processing could not be completed.";
        setError(message);
        toast.error(message);
      }
    } finally {
      setApproving(false);
    }
  }, [approving, project, projectId, router, watchJob]);

  // Resume watching an in-flight job after a reload / session bounce so the
  // page reflects real progress instead of the stale pre-processing state.
  useEffect(() => {
    if (!project || approving) return;
    let cancelled = false;
    (async () => {
      try {
        const jobs = await processApi.listProjectJobs(projectId);
        const active = jobs.find((j) =>
          j.job_type === "process" &&
          ["created", "processing_queued", "processing", "encoding"].includes(j.status),
        );
        if (!active || cancelled) return;
        setApproving(true);
        try {
          await watchJob(active.id);
        } finally {
          if (!cancelled) setApproving(false);
        }
      } catch {
        // Non-fatal: resume is best-effort.
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id]);

  const download = useCallback(async () => {
    if (!project) return;
    setDownloading(true);
    setError(null);
    try {
      const issued = await downloadApi.issueUrl(projectId);
      const token = issued.url.startsWith("token:") ? issued.url.slice("token:".length) : issued.url;
      const response = await fetch(downloadApi.streamUrl(projectId, token));
      if (!response.ok) throw new Error(`Download failed (HTTP ${response.status}).`);
      const objectUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = project.original_filename
        ? project.original_filename.replace(/\.[^.]+$/, "") + "_cleaned.mp4"
        : `${projectId}_output.mp4`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
      toast.success("Download started.");
    } catch (reason) {
      const apiError = reason as ApiError;
      const message = apiError?.message || "Download failed. Please try again.";
      setError(message);
      toast.error(message);
    } finally {
      setDownloading(false);
    }
  }, [project, projectId]);

  // Only the signed URL from the project payload works in a <video src> —
  // the tokenless /preview-clip route needs an Authorization header, which
  // media elements can't send, so falling back to it just rendered a 401.
  const clipUrl = project?.preview_url || null;
  const beforeClipUrl = project?.before_preview_url || project?.proxy_url || null;
  const beforeTimeOffset = project?.before_preview_url ? 0 : start;

  const syncBeforeVideo = useCallback(() => {
    const before = beforeVideoRef.current;
    const after = afterVideoRef.current;
    if (!before || !after || before.readyState < 1 || !Number.isFinite(after.currentTime)) return;
    const expected = beforeTimeOffset + after.currentTime;
    if (Math.abs(before.currentTime - expected) > 0.05) before.currentTime = expected;
    if (!after.paused && before.paused) void before.play().catch(() => undefined);
  }, [beforeTimeOffset]);

  useEffect(() => {
    const before = beforeVideoRef.current;
    const after = afterVideoRef.current;
    if (!before || !after) return;
    let frame: number | null = null;
    const keepAligned = () => {
      syncBeforeVideo();
      if (!after.paused) frame = requestAnimationFrame(keepAligned);
    };
    const startAlignment = () => {
      if (frame !== null) cancelAnimationFrame(frame);
      keepAligned();
    };
    const pauseBefore = () => before.pause();
    after.addEventListener("loadedmetadata", startAlignment);
    after.addEventListener("play", startAlignment);
    after.addEventListener("timeupdate", syncBeforeVideo);
    after.addEventListener("seeking", startAlignment);
    after.addEventListener("pause", pauseBefore);
    before.addEventListener("loadedmetadata", startAlignment);
    startAlignment();
    return () => {
      if (frame !== null) cancelAnimationFrame(frame);
      after.removeEventListener("loadedmetadata", startAlignment);
      after.removeEventListener("play", startAlignment);
      after.removeEventListener("timeupdate", syncBeforeVideo);
      after.removeEventListener("seeking", startAlignment);
      after.removeEventListener("pause", pauseBefore);
      before.removeEventListener("loadedmetadata", startAlignment);
    };
  }, [beforeClipUrl, clipUrl, syncBeforeVideo]);

  if (!project) {
    return (
      <AppShell title="Preview and approve" eyebrow="Project workflow">
        <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8">
          {error ? <ErrorBanner message={error} /> : <div className="h-72 animate-pulse rounded-3xl border border-white/10 bg-white/[.04] motion-reduce:animate-none" />}
        </div>
      </AppShell>
    );
  }

  const filename = project.title || project.original_filename;
  const hasPreview = Boolean(clipUrl && beforeClipUrl);
  const progress = job?.progress || 0;
  const estimatedTime = (project.width || 0) >= 1920 ? "about 3 to 6 minutes" : "about 1 to 3 minutes";

  return (
    <AppShell title="Preview and approve" eyebrow="Project workflow">
      <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
        <WorkflowStepper current={4} />

        <header className="mt-8 flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[.18em] text-[#9eb4ff]">Final quality check</p>
            <h2 className="mt-2 max-w-3xl truncate text-2xl font-semibold tracking-tight sm:text-3xl" title={filename}>{filename}</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              <MetadataBadge>{project.width || "?"}&times;{project.height || "?"}</MetadataBadge>
              <MetadataBadge>{project.video_codec || "Unknown codec"}</MetadataBadge>
              <MetadataBadge>{project.duration?.toFixed(1) || "?"}s</MetadataBadge>
              {project.fps && <MetadataBadge>{project.fps.toFixed(2)} fps</MetadataBadge>}
            </div>
          </div>
          <Link href="/dashboard" className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-sm text-white/60 transition hover:bg-white/5 hover:text-white">Back to projects</Link>
        </header>

        <section className="mt-7 rounded-2xl border border-white/10 bg-[#10121f] p-5 sm:p-6">
          <div className="flex flex-wrap items-end gap-5">
            <label htmlFor="preview-start" className="block text-sm font-medium text-white/70">
              Start (seconds)
              <input
                id="preview-start"
                type="number"
                min={0}
                max={Math.max(0, (project.duration || 0) - duration)}
                value={start}
                onChange={(event) => setStart(Math.max(0, Number(event.target.value)))}
                className="mt-2 block h-11 w-28 rounded-xl border border-white/10 bg-white/5 px-3 text-base text-white outline-none transition focus:border-[#4f7cff] focus:ring-2 focus:ring-[#4f7cff]/30"
              />
            </label>
            <fieldset>
              <legend className="text-sm font-medium text-white/70">Window length</legend>
              <div className="mt-2 inline-flex rounded-xl border border-white/10 bg-black/25 p-1">
                {DURATIONS.map((option) => (
                  <button
                    type="button"
                    key={option}
                    onClick={() => setDuration(option)}
                    aria-pressed={duration === option}
                    className={`min-h-9 min-w-14 rounded-lg px-3 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4f7cff] ${duration === option ? "bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] text-white shadow-lg" : "text-white/50 hover:bg-white/5 hover:text-white"}`}
                  >
                    {option}s
                  </button>
                ))}
              </div>
            </fieldset>
            <label className="flex min-h-11 items-center gap-3 rounded-xl px-1 text-sm text-white/65">
              <input type="checkbox" checked={loop} onChange={(event) => setLoop(event.target.checked)} className="h-5 w-5 accent-[#4f7cff]" />
              Loop playback
            </label>
            <div className="ml-auto text-right">
              <span className="mb-2 hidden items-center justify-end gap-1.5 text-xs text-[#9eb4ff] sm:flex"><ArrowUpRight className="h-3.5 w-3.5" />Start here</span>
              <button
                type="button"
                onClick={() => void buildPreview()}
                disabled={building}
                className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_10px_28px_rgba(79,124,255,.24)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {building ? <><LoaderCircle className="h-4 w-4 animate-spin motion-reduce:animate-none" />Building {buildProgress}%</> : <><Sparkles className="h-4 w-4" />{hasPreview ? "Rebuild preview" : "Build preview"}</>}
              </button>
            </div>
          </div>
        </section>

        <section className="mt-6 overflow-hidden rounded-3xl border border-white/10 bg-black shadow-[0_24px_80px_rgba(0,0,0,.35)]" aria-label="Before and after video comparison">
          {building ? (
            <PreviewBuilding progress={buildProgress} />
          ) : hasPreview ? (
            <div className="relative">
              <ReactCompareSlider
                className="aspect-video w-full bg-black"
                defaultPosition={50}
                keyboardIncrement="5%"
                handle={<ReactCompareSliderHandle buttonStyle={{ background: "rgba(10,11,15,.8)", borderColor: "#22d3ee", width: 52, height: 52 }} linesStyle={{ color: "#22d3ee", width: 2 }} />}
                itemOne={<VideoPane label="Before" videoRef={beforeVideoRef} src={beforeClipUrl!} loop={loop} />}
                itemTwo={<VideoPane label="After" videoRef={afterVideoRef} src={clipUrl!} loop={loop} />}
              />
              <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-between bg-gradient-to-t from-black/80 to-transparent px-4 pb-4 pt-12 text-xs font-semibold uppercase tracking-[.14em]">
                <span className="rounded-full bg-black/60 px-3 py-1.5 text-white/70">Before</span>
                <span className="rounded-full bg-cyan-400/15 px-3 py-1.5 text-cyan-200">After cleanup</span>
              </div>
            </div>
          ) : (
            <PreviewEmpty onBuild={() => void buildPreview()} />
          )}
        </section>

        {error && <div className="mt-5"><ErrorBanner message={error} /></div>}

        {approving && job && (
          <section className="mt-6 rounded-2xl border border-[#4f7cff]/25 bg-[#4f7cff]/[.08] p-5" aria-live="polite">
            <div className="flex items-center justify-between gap-4 text-sm"><span className="font-medium text-white">{prettyStage(job)}</span><span className="font-mono text-[#b7c7ff]">{progress}%</span></div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-[#4f7cff] via-cyan-400 to-[#6d5ef7] transition-[width] duration-300 motion-reduce:transition-none" style={{ width: `${progress}%` }} /></div>
            <p className="mt-3 text-xs text-white/45">{job.frames_processed} of {job.total_frames || "?"} frames processed. You can leave this page; completion will appear as a notification.</p>
          </section>
        )}

        <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_1.25fr]">
          <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5 sm:p-6">
            <div className="flex items-center gap-3"><ShieldCheck className="h-5 w-5 text-emerald-300" /><h3 className="font-semibold">What stays preserved</h3></div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <Preserved label="Original audio" value={project.has_audio === false ? "No source audio" : "Preserved"} />
              <Preserved label="Resolution" value={`${project.width || "?"} x ${project.height || "?"}`} />
              <Preserved label="Frame rate" value={project.fps ? `${project.fps.toFixed(2)} fps` : "Source rate"} />
              <Preserved label="Duration" value={`${project.duration?.toFixed(1) || "?"} seconds`} />
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#10121f] to-[#11152a] p-5 sm:p-6">
            <div className="flex items-start gap-3"><Clock3 className="mt-0.5 h-5 w-5 shrink-0 text-[#9eb4ff]" /><div><h3 className="font-semibold">Ready for the full-resolution render?</h3><p className="mt-2 max-w-2xl text-sm leading-6 text-white/55">We will process all {project.duration?.toFixed(1) || "?"} seconds at full resolution. This usually takes {estimatedTime}. You will be notified when the cleaned video is ready.</p></div></div>
            <div className="mt-6 flex flex-col gap-3 sm:flex-row">
              {project.status === "completed" ? (
                <button type="button" onClick={() => void download()} disabled={downloading} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-[#06120d] transition hover:bg-emerald-400 disabled:opacity-50"><Download className="h-4 w-4" />{downloading ? "Preparing download..." : "Download cleaned video"}</button>
              ) : (
                <button ref={approveButtonRef} type="button" onClick={() => setConfirming(true)} disabled={!hasPreview || approving} title={!hasPreview ? "Build and review a preview first" : undefined} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-[#06120d] transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"><CheckCircle2 className="h-4 w-4" />{approving ? "Processing full video..." : "Approve and process full video"}</button>
              )}
              <button type="button" onClick={() => router.push(`/projects/${projectId}`)} className="min-h-11 rounded-xl border border-white/10 px-5 py-2.5 text-sm font-medium text-white/55 transition hover:bg-white/5 hover:text-white">Return to mask editor</button>
            </div>
            {!hasPreview && <p className="mt-3 text-xs text-amber-200/70">Build and review a preview before approving the full render.</p>}
          </section>
        </div>

        <p className="mt-5 flex items-center gap-2 text-xs text-white/35"><Gauge className="h-3.5 w-3.5" />Tip: inspect edges and moving areas by dragging the comparison handle slowly across the frame.</p>
      </div>

      {confirming && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/65 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.currentTarget === event.target) setConfirming(false); }}>
          <section role="dialog" aria-modal="true" aria-labelledby="approve-title" className="w-full max-w-lg rounded-3xl border border-white/10 bg-[#10121f] p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4"><div className="grid h-11 w-11 place-items-center rounded-2xl bg-emerald-400/15 text-emerald-300"><Film className="h-5 w-5" /></div><button type="button" onClick={() => setConfirming(false)} aria-label="Close confirmation" className="grid h-11 w-11 place-items-center rounded-xl text-white/45 hover:bg-white/5 hover:text-white"><X className="h-5 w-5" /></button></div>
            <h2 id="approve-title" className="mt-5 text-xl font-semibold">Process the full video?</h2>
            <p className="mt-3 text-sm leading-6 text-white/55">ClearFrame will render all {project.duration?.toFixed(1) || "?"} seconds at {project.width || "?"} x {project.height || "?"}. Estimated time: {estimatedTime}.</p>
            <div className="mt-5 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-white/60"><p className="font-medium text-white/80">What happens next</p><p className="mt-2 leading-6">Live progress will appear on this page. When processing finishes, you will receive a toast and the download action will unlock.</p></div>
            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end"><button type="button" onClick={() => setConfirming(false)} className="min-h-11 rounded-xl border border-white/10 px-4 py-2.5 text-sm text-white/60 hover:bg-white/5 hover:text-white">Keep reviewing</button><button type="button" autoFocus onClick={() => void beginProcessing()} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-[#06120d] hover:bg-emerald-400">Start full processing <ChevronRight className="h-4 w-4" /></button></div>
          </section>
        </div>
      )}
    </AppShell>
  );
}

function VideoPane({ label, videoRef, src, loop }: { label: string; videoRef: React.RefObject<HTMLVideoElement>; src: string; loop: boolean }) {
  return <div className="relative h-full w-full bg-black"><video ref={videoRef} src={src} aria-label={`${label} preview`} autoPlay loop={loop} muted playsInline className="h-full w-full object-contain" /></div>;
}

function PreviewEmpty({ onBuild }: { onBuild: () => void }) {
  return <div className="grid min-h-[360px] place-items-center px-6 py-14 text-center sm:aspect-video sm:min-h-0"><div><div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl border border-[#4f7cff]/20 bg-gradient-to-br from-[#4f7cff]/20 to-[#6d5ef7]/10 text-[#9eb4ff]"><Film className="h-7 w-7" /></div><h3 className="mt-5 text-xl font-semibold">See the cleanup before you commit</h3><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-white/50">Choose a short window, build the preview, then drag the handle to inspect the original and cleaned frames side by side.</p><button type="button" onClick={onBuild} className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-xl border border-[#4f7cff]/30 bg-[#4f7cff]/10 px-5 py-2.5 text-sm font-semibold text-[#b7c7ff] hover:bg-[#4f7cff]/20"><Sparkles className="h-4 w-4" />Build the comparison</button></div></div>;
}

function PreviewBuilding({ progress }: { progress: number }) {
  return <div className="relative grid min-h-[360px] place-items-center overflow-hidden px-6 py-14 text-center sm:aspect-video sm:min-h-0" aria-live="polite"><div className="absolute inset-0 animate-pulse bg-[linear-gradient(110deg,#07080f_20%,#15192a_45%,#07080f_70%)] bg-[length:220%_100%] motion-reduce:animate-none" /><div className="relative z-10 w-full max-w-md"><div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-[#4f7cff]/15 text-[#9eb4ff]"><LoaderCircle className="h-6 w-6 animate-spin motion-reduce:animate-none" /></div><h3 className="mt-5 text-lg font-semibold">Rendering your comparison</h3><p className="mt-2 text-sm text-white/45">Applying the saved mask to this preview window.</p><div className="mt-6 h-2 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-[#4f7cff] via-cyan-400 to-[#6d5ef7] transition-[width] duration-300 motion-reduce:transition-none" style={{ width: `${progress}%` }} /></div><p className="mt-2 font-mono text-xs text-white/45">{progress}%</p></div></div>;
}

function MetadataBadge({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full border border-white/10 bg-white/[.04] px-3 py-1 text-xs text-white/55">{children}</span>;
}

function Preserved({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center gap-3 rounded-xl border border-white/[.07] bg-black/15 p-3"><span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-emerald-400/10 text-emerald-300"><Check className="h-4 w-4" /></span><div><p className="text-xs text-white/40">{label}</p><p className="mt-0.5 text-sm font-medium text-white/75">{value}</p></div></div>;
}

function ErrorBanner({ message }: { message: string }) {
  return <div role="alert" className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{message}</div>;
}

function prettyStage(job: JobStatus) {
  return (job.current_stage || job.status).replace(/_/g, " ").replace(/(^| )\w/g, (letter) => letter.toUpperCase());
}

function emptyPreview(): PreviewResponse {
  return { project_id: "", status: "queued", quality_mode: "balanced", start_seconds: 0, duration_seconds: 5 };
}
