"use client";
// Worker detail (PRD §12.3): fused online state, GPU, active job, lifetime
// throughput, and recent job history. Live-polls every 8s.
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import type { AdminJob } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, Stat } from "@/components/admin/ui";

export default function AdminWorkerDetailPage() {
  const { name } = useParams<{ name: string }>();
  const router = useRouter();
  const workerName = decodeURIComponent(name);

  const { data: worker, error, isLoading } = useQuery({
    queryKey: ["admin", "worker", workerName],
    queryFn: () => adminApi.getWorker(workerName),
    refetchInterval: 8000,
  });

  if (error) return <ErrorNote text="Unable to load this worker." />;
  if (isLoading || !worker) return <LoadingBlock />;

  const total = worker.completed_count + worker.failed_count;
  const successRate = total > 0 ? Math.round((worker.completed_count / total) * 100) : null;

  return (
    <div className="space-y-6">
      <button onClick={() => router.push("/admin/workers")} className="text-sm text-[#9eb4ff] hover:text-white">← All workers</button>

      <section className="rounded-2xl border border-white/10 bg-[#10121f] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-mono text-lg text-white">{worker.name}</h1>
              <Badge status={worker.online ? "online" : "offline"} />
              {worker.status && <span className="text-xs text-white/45">{worker.status}</span>}
            </div>
            <p className="mt-2 text-sm text-white/50">
              {worker.gpu_name || "No GPU reported"}
              {worker.gpu_memory ? ` · ${(worker.gpu_memory / 1024).toFixed(0)} GB` : ""}
              {worker.software_version ? ` · v${worker.software_version}` : ""}
            </p>
            <p className="mt-1 text-xs text-white/35">
              Last heartbeat: {worker.last_heartbeat ? new Date(worker.last_heartbeat).toLocaleString() : "never"}
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Completed" value={worker.completed_count} tone="border-emerald-400/20 bg-emerald-400/[.06]" />
        <Stat label="Failed" value={worker.failed_count} tone={worker.failed_count > 0 ? "border-rose-400/25 bg-rose-400/[.08]" : undefined} />
        <Stat label="Success rate" value={successRate == null ? "—" : `${successRate}%`} />
        <Stat label="Active job" value={worker.active_job ? worker.active_job.id.slice(0, 8) : "idle"} />
      </div>

      {worker.active_job && (
        <section className="rounded-2xl border border-[#4f7cff]/25 bg-[#4f7cff]/[.06] p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-white/50">Currently processing</h3>
          <button
            onClick={() => router.push(`/admin/jobs/${worker.active_job!.id}`)}
            className="mt-3 flex w-full items-center justify-between gap-3 text-left"
          >
            <span className="font-mono text-sm text-white">{worker.active_job.id.slice(0, 12)}…</span>
            <span className="flex items-center gap-3">
              <span className="text-xs text-white/50">{worker.active_job.progress}%</span>
              <Badge status={worker.active_job.status} />
            </span>
          </button>
        </section>
      )}

      <section className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-white/40">Recent jobs</h3>
        <DataTable<AdminJob>
          rows={worker.recent_jobs}
          rowKey={(j) => j.id}
          onRowClick={(j) => router.push(`/admin/jobs/${j.id}`)}
          empty="No jobs attributed to this worker."
          columns={[
            { key: "id", header: "Job", render: (j) => <span className="font-mono text-xs">{j.id.slice(0, 8)}</span> },
            { key: "type", header: "Type", render: (j) => j.job_type },
            { key: "status", header: "Status", render: (j) => <Badge status={j.status} /> },
            { key: "error", header: "Error", render: (j) => <span className="text-xs text-rose-300">{j.error_code || "—"}</span> },
            { key: "created", header: "Created", render: (j) => <span className="text-xs text-white/50">{new Date(j.created_at).toLocaleString()}</span> },
          ]}
        />
      </section>
    </div>
  );
}
