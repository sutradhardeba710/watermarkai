"use client";
// Queue metrics (PRD §11): depth + throughput dashboard with per-queue
// breakdown. Live-polls every 10s.
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import type { QueueInfo } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, PageHeader, Stat } from "@/components/admin/ui";

function fmtAge(s?: number | null): string {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`;
  return `${(s / 3600).toFixed(1)}h`;
}

export default function AdminQueuePage() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "queues"],
    queryFn: adminApi.getQueues,
    refetchInterval: 10_000,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Infrastructure"
        title="Queues"
        subtitle="Backlog depth and throughput across the detection and processing queues."
      />
      {error && <ErrorNote text="Unable to load queue metrics." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Queued" value={data.queued} tone={data.queued > 20 ? "border-amber-400/30 bg-amber-400/10" : undefined} hint="waiting for a worker" />
            <Stat label="Active" value={data.active} hint="running now" />
            <Stat label="Completed today" value={data.completed_today} tone="border-emerald-400/20 bg-emerald-400/[.06]" />
            <Stat label="Failed today" value={data.failed_today} tone={data.failed_today > 0 ? "border-rose-400/25 bg-rose-400/[.08]" : undefined} />
          </div>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-white/40">Per-queue</h3>
            <DataTable<QueueInfo>
              rows={data.queues}
              rowKey={(q) => q.name}
              empty="No queues."
              columns={[
                { key: "name", header: "Queue", render: (q) => <span className="font-medium capitalize text-white">{q.name}</span> },
                { key: "queued", header: "Queued", render: (q) => q.queued },
                { key: "active", header: "Active", render: (q) => q.active },
                { key: "failed", header: "Failed today", render: (q) => <span className={q.failed_today > 0 ? "text-rose-300" : "text-white/60"}>{q.failed_today}</span> },
                { key: "oldest", header: "Oldest wait", render: (q) => <span className="text-xs text-white/55">{fmtAge(q.oldest_queued_seconds)}</span> },
              ]}
            />
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-white/40">Jobs by state</h3>
            <div className="flex flex-wrap gap-2 rounded-2xl border border-white/10 bg-[#10121f] p-5">
              {Object.entries(data.by_state).length === 0 ? (
                <p className="text-sm text-white/40">No jobs recorded.</p>
              ) : (
                Object.entries(data.by_state)
                  .sort((a, b) => b[1] - a[1])
                  .map(([state, count]) => (
                    <span key={state} className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#0c0e1a] px-3 py-2">
                      <Badge status={state} />
                      <span className="text-sm font-semibold text-white">{count}</span>
                    </span>
                  ))
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
