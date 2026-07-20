"use client";
// Job monitoring (ADMIN-003 / PRD §10) with retry/cancel actions.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AdminJob } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";
import { ConfirmActionDialog, ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

const STATUSES = ["", "created", "processing_queued", "processing", "completed", "failed", "cancelled"];

export default function AdminJobsPage() {
  const user = useAuthStore((s) => s.user);
  const router = useRouter();
  const canManage = hasPermission(user, "jobs.manage");
  const [status, setStatus] = useState("");
  const [dialog, setDialog] = useState<ConfirmActionState | null>(null);
  const qc = useQueryClient();

  const { data: jobs, error, isLoading } = useQuery({
    queryKey: ["admin", "jobs", status],
    queryFn: () => adminApi.listJobs(status ? { status } : {}),
    refetchInterval: 15_000,
  });

  function act(job: AdminJob, action: "retry" | "cancel") {
    setDialog({
      title: action === "retry" ? "Retry job" : "Cancel job",
      description: `${action === "retry" ? "Re-enqueue" : "Cancel"} ${job.job_type} job ${job.id.slice(0, 8)}…?`,
      confirmLabel: action === "retry" ? "Retry" : "Cancel job",
      danger: action === "cancel",
      onConfirm: async () => {
        await adminApi.actOnJob(job.id, action);
        toast.success(action === "retry" ? "Job re-enqueued." : "Job cancelled.");
        qc.invalidateQueries({ queryKey: ["admin", "jobs"] });
      },
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Processing"
        title="Jobs"
        subtitle="Every analysis, preview, and processing job across the platform."
        actions={
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-10 rounded-xl border border-white/10 bg-[#10121f] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s ? s.replaceAll("_", " ") : "All statuses"}</option>
            ))}
          </select>
        }
      />
      {error && <ErrorNote text="Unable to load jobs." />}
      {isLoading ? (
        <LoadingBlock />
      ) : (
        <DataTable<AdminJob>
          rows={jobs || []}
          rowKey={(j) => j.id}
          onRowClick={(j) => router.push(`/admin/jobs/${j.id}`)}
          empty="No jobs found."
          columns={[
            { key: "id", header: "Job", render: (j) => <span className="font-mono text-xs">{j.id.slice(0, 8)}</span> },
            { key: "type", header: "Type", render: (j) => j.job_type },
            { key: "status", header: "Status", render: (j) => <Badge status={j.status} /> },
            {
              key: "progress", header: "Progress", render: (j) => (
                <div className="w-32">
                  <div className="flex justify-between text-[11px] text-white/45"><span>{j.progress}%</span></div>
                  <div className="mt-1 h-1 rounded-full bg-white/10">
                    <div className="h-full rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6]" style={{ width: `${j.progress}%` }} />
                  </div>
                </div>
              ),
            },
            { key: "worker", header: "Worker", render: (j) => <span className="text-xs text-white/55">{j.worker_id || "—"}</span> },
            { key: "error", header: "Error", render: (j) => <span className="text-xs text-rose-300">{j.error_code || "—"}</span> },
            {
              key: "actions", header: "", className: "text-right", render: (j) => canManage ? (
                <div className="flex justify-end gap-2" onClick={(e) => e.stopPropagation()}>
                  {(j.status === "failed" || j.status === "cancelled") && (
                    <button onClick={() => act(j, "retry")} className="rounded-lg border border-emerald-400/20 px-3 py-1.5 text-xs text-emerald-300 hover:bg-emerald-400/10">Retry</button>
                  )}
                  {!["completed", "failed", "cancelled", "expired"].includes(j.status) && (
                    <button onClick={() => act(j, "cancel")} className="rounded-lg border border-rose-400/20 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-400/10">Cancel</button>
                  )}
                </div>
              ) : null,
            },
          ]}
        />
      )}
      <ConfirmActionDialog state={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}
