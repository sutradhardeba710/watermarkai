"use client";
// Worker monitoring (ADMIN-004 / PRD §12).
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import type { WorkerInfo } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";

export default function AdminWorkersPage() {
  const router = useRouter();
  const { data: workers, error, isLoading } = useQuery({
    queryKey: ["admin", "workers"],
    queryFn: adminApi.listWorkers,
    refetchInterval: 15_000,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Infrastructure"
        title="Workers"
        subtitle="Celery worker nodes with heartbeat, GPU, and active job."
      />
      {error && <ErrorNote text="Unable to load workers." />}
      {isLoading ? (
        <LoadingBlock />
      ) : (
        <DataTable<WorkerInfo>
          rows={workers || []}
          rowKey={(w) => w.name}
          onRowClick={(w) => router.push(`/admin/workers/${encodeURIComponent(w.name)}`)}
          empty="No workers registered."
          columns={[
            { key: "name", header: "Worker", render: (w) => <span className="font-mono text-xs">{w.name}</span> },
            { key: "state", header: "State", render: (w) => <Badge status={w.online ? "online" : "offline"} /> },
            { key: "status", header: "Status", render: (w) => <span className="text-xs text-white/55">{w.status || "—"}</span> },
            { key: "gpu", header: "GPU", render: (w) => w.gpu_name || "—" },
            { key: "job", header: "Active job", render: (w) => <span className="text-xs text-white/55">{w.active_job_id || "—"}</span> },
            {
              key: "heartbeat", header: "Last heartbeat", render: (w) => (
                <span className="text-xs text-white/45">
                  {w.last_heartbeat ? new Date(w.last_heartbeat).toLocaleString() : "never"}
                </span>
              ),
            },
            { key: "version", header: "Version", render: (w) => <span className="text-xs text-white/45">{w.software_version || "—"}</span> },
          ]}
        />
      )}
    </div>
  );
}
