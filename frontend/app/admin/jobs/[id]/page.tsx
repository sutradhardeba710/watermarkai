"use client";
// Job detail (PRD §10.3–10.4): stage timeline, timing, failure diagnostics,
// recent audit events + retry/cancel. Live-polls while the job is non-terminal.
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AdminJobDetail, JobStageStep } from "@/types";
import { Badge, ErrorNote, LoadingBlock, Stat } from "@/components/admin/ui";
import { ConfirmActionDialog, ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

const TERMINAL = ["completed", "failed", "cancelled", "expired"];

function fmtSeconds(s?: number | null): string {
  if (s == null) return "—";
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = Math.round(s % 60);
  return `${m}m ${rem}s`;
}

export default function AdminJobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const me = useAuthStore((s) => s.user);
  const canManage = hasPermission(me, "jobs.manage");
  const qc = useQueryClient();
  const [dialog, setDialog] = useState<ConfirmActionState | null>(null);

  const { data: job, error, isLoading } = useQuery({
    queryKey: ["admin", "job", id],
    queryFn: () => adminApi.getJob(id),
    // Live updates while the job is still running; stop once terminal.
    refetchInterval: (query) => {
      const j = query.state.data as AdminJobDetail | undefined;
      return j && TERMINAL.includes(j.status) ? false : 4000;
    },
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "job", id] });
    qc.invalidateQueries({ queryKey: ["admin", "jobs"] });
  }

  function act(action: "retry" | "cancel") {
    if (!job) return;
    setDialog({
      title: action === "retry" ? "Retry job" : "Cancel job",
      description: `${action === "retry" ? "Re-enqueue" : "Cancel"} this ${job.job_type} job?`,
      confirmLabel: action === "retry" ? "Retry" : "Cancel job",
      danger: action === "cancel",
      onConfirm: async () => {
        await adminApi.actOnJob(job.id, action);
        toast.success(action === "retry" ? "Job re-enqueued." : "Job cancelled.");
        refresh();
      },
    });
  }

  if (error) return <ErrorNote text="Unable to load this job." />;
  if (isLoading || !job) return <LoadingBlock />;

  const isTerminal = TERMINAL.includes(job.status);

  return (
    <div className="space-y-6">
      <button onClick={() => router.push("/admin/jobs")} className="text-sm text-[#9eb4ff] hover:text-white">← All jobs</button>

      {/* Header */}
      <section className="rounded-2xl border border-white/10 bg-[#10121f] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-mono text-lg text-white">{job.id.slice(0, 12)}…</h1>
              <Badge status={job.status} />
            </div>
            <p className="mt-2 text-sm text-white/50">
              {job.job_type} · {job.processing_mode}
              {job.project_title ? ` · ${job.project_title}` : ""}
              {job.user_email ? ` · ${job.user_email}` : ""}
            </p>
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-white/40">
              <button onClick={() => router.push(`/admin/projects/${job.project_id}`)} className="hover:text-white">
                Project {job.project_id.slice(0, 8)}
              </button>
              <button onClick={() => router.push(`/admin/users/${job.user_id}`)} className="hover:text-white">
                User {job.user_id.slice(0, 8)}
              </button>
              {job.worker_id && (
                <button onClick={() => router.push(`/admin/workers/${encodeURIComponent(job.worker_id!)}`)} className="hover:text-white">
                  Worker {job.worker_id}
                </button>
              )}
            </div>
          </div>
          {canManage && (
            <div className="flex gap-2">
              {(job.status === "failed" || job.status === "cancelled") && (
                <button onClick={() => act("retry")} className="rounded-lg border border-emerald-400/20 px-3 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-400/10">Retry</button>
              )}
              {!isTerminal && (
                <button onClick={() => act("cancel")} className="rounded-lg border border-rose-400/20 px-3 py-1.5 text-xs font-semibold text-rose-300 hover:bg-rose-400/10">Cancel</button>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Metrics */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Progress" value={`${job.progress}%`} hint={job.current_stage || undefined} />
        <Stat label="Frames" value={`${job.frames_processed}/${job.total_frames || "?"}`} />
        <Stat label="Queued for" value={fmtSeconds(job.queued_seconds)} />
        <Stat label="Run time" value={fmtSeconds(job.duration_seconds)} hint={`Attempt ${job.attempt_count}`} />
      </div>

      {/* Progress bar */}
      <div className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
        <div className="flex justify-between text-xs text-white/45"><span>{job.current_stage || job.status}</span><span>{job.progress}%</span></div>
        <div className="mt-2 h-2 rounded-full bg-white/10">
          <div className="h-full rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] transition-all" style={{ width: `${job.progress}%` }} />
        </div>
      </div>

      {/* Stage timeline */}
      <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-white/40">Stage timeline</h3>
        <ol className="mt-4 space-y-3">
          {job.timeline.map((step) => <TimelineStep key={step.stage} step={step} />)}
        </ol>
      </section>

      {/* Failure diagnostics */}
      {(job.error_code || job.error_message) && (
        <section className="rounded-2xl border border-rose-400/20 bg-rose-500/10 p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-rose-200">Failure diagnostics</h3>
          {job.error_code && <p className="mt-2 font-mono text-xs text-rose-300">{job.error_code}</p>}
          {job.error_message && <p className="mt-2 whitespace-pre-wrap text-sm text-rose-100/80">{job.error_message}</p>}
        </section>
      )}

      {/* Recent audit events */}
      <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-white/40">Recent admin events</h3>
        {job.recent_events.length === 0 ? (
          <p className="mt-3 text-sm text-white/40">No admin actions recorded for this job.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {job.recent_events.map((e) => (
              <li key={e.id} className="flex items-center justify-between gap-3 text-xs">
                <span className="flex items-center gap-2"><Badge status={e.action} /><span className="text-white/45">{e.reason || ""}</span></span>
                <span className="text-white/35">{new Date(e.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <ConfirmActionDialog state={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}

function TimelineStep({ step }: { step: JobStageStep }) {
  const dot =
    step.state === "done" ? "bg-emerald-400 border-emerald-400"
      : step.state === "current" ? "bg-[#4f7cff] border-[#4f7cff] animate-pulse"
        : step.state === "failed" || step.state === "cancelled" || step.state === "expired" ? "bg-rose-400 border-rose-400"
          : "bg-transparent border-white/20";
  const text =
    step.state === "pending" ? "text-white/35"
      : step.state === "failed" || step.state === "cancelled" || step.state === "expired" ? "text-rose-300"
        : "text-white/80";
  return (
    <li className="flex items-center gap-3">
      <span className={`h-3 w-3 rounded-full border ${dot}`} />
      <span className={`text-sm ${text}`}>{step.label}</span>
      {step.state === "current" && <span className="text-[11px] text-[#9eb4ff]">in progress</span>}
    </li>
  );
}
