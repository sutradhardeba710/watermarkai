"use client";
// Storage & retention dashboard (PRD §18). Shows per-bucket footprint + an
// estimated monthly spend, and lists output files by retention state so an
// operator can extend, expire, or retry cleanup. Deletion-adjacent actions are
// refused server-side (§18.5) when a project is on legal hold / locked / busy.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { RetentionItem, StorageAction } from "@/types";
import {
  Badge, DataTable, ErrorNote, formatINR, LoadingBlock, PageHeader, Pagination, Stat,
} from "@/components/admin/ui";
import { ConfirmActionDialog, ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

function formatBytes(n?: number | null): string {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export default function AdminStoragePage() {
  const user = useAuthStore((s) => s.user);
  const canManage = hasPermission(user, "projects.manage");
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<ConfirmActionState | null>(null);
  const qc = useQueryClient();

  const overview = useQuery({
    queryKey: ["admin", "storage", "overview"],
    queryFn: () => adminApi.storageOverview(),
  });
  const retention = useQuery({
    queryKey: ["admin", "storage", "retention", page],
    queryFn: () => adminApi.retentionDashboard({ page, page_size: 25 }),
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "storage"] });
  }

  function act(item: RetentionItem, action: StorageAction) {
    const meta: Record<StorageAction, { title: string; danger?: boolean; hours?: boolean }> = {
      extend_retention: { title: "Extend retention" },
      expire_now: { title: "Expire now", danger: true },
      trigger_cleanup: { title: "Delete files now", danger: true },
      retry_cleanup: { title: "Retry cleanup", danger: true },
      lock_compliance: { title: "Lock for compliance" },
      verify_existence: { title: "Verify files exist" },
    };
    const m = meta[action];
    setDialog({
      title: m.title,
      description: `${m.title} for project ${item.project_id.slice(0, 8)}… (${item.project_title || "untitled"}).`,
      confirmLabel: m.title,
      danger: m.danger,
      requireReason: action !== "verify_existence" && action !== "extend_retention",
      numberLabel: action === "extend_retention" ? "Additional hours" : undefined,
      numberDefault: 168,
      onConfirm: async (reason, amount) => {
        const res = await adminApi.actOnStorage(item.project_id, {
          action,
          reason: reason || undefined,
          hours: action === "extend_retention" ? amount : undefined,
        });
        if (action === "verify_existence") {
          const exists = (res.result?.exists ?? {}) as Record<string, boolean>;
          const missing = Object.entries(exists).filter(([, ok]) => !ok).map(([b]) => b);
          if (missing.length) toast.warning(`Missing: ${missing.join(", ")}`);
          else toast.success("All recorded files exist.");
        } else {
          toast.success("Storage action applied.");
        }
        refresh();
      },
    });
  }

  const ov = overview.data;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Storage"
        title="Storage & retention"
        subtitle="Bucket footprint, estimated spend, and files approaching their retention cutoff."
      />
      {overview.error && <ErrorNote text="Unable to load storage overview." />}
      {overview.isLoading || !ov ? (
        <LoadingBlock />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Total stored" value={formatBytes(ov.total_bytes)} />
            <Stat label="Est. cost / month" value={formatINR(ov.estimated_cost_inr)} hint="₹2 / GB-month" />
            <Stat label="Output files" value={ov.key_counts?.output ?? 0} />
            <Stat
              label="Orphaned"
              value={formatBytes(ov.buckets?.orphaned ?? 0)}
              tone={ov.buckets?.orphaned ? "border-amber-400/20 bg-amber-400/10" : undefined}
            />
          </div>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">Buckets</h2>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {Object.entries(ov.buckets).map(([bucket, bytes]) => (
                <div key={bucket} className="rounded-xl border border-white/10 bg-[#10121f] p-3">
                  <p className="text-xs uppercase tracking-wide text-white/40">{bucket}</p>
                  <p className="mt-1 text-lg font-semibold text-white">{formatBytes(bytes)}</p>
                  <p className="text-xs text-white/35">{ov.key_counts?.[bucket] ?? 0} keys</p>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">Retention queue</h2>
        {retention.error && <ErrorNote text="Unable to load retention queue." />}
        {retention.isLoading || !retention.data ? (
          <LoadingBlock />
        ) : (
          <>
            <DataTable<RetentionItem>
              rows={retention.data.items}
              rowKey={(r) => r.output_id}
              empty="No output files are being tracked."
              columns={[
                {
                  key: "project", header: "Project", render: (r) => (
                    <div>
                      <p className="text-sm text-white/80">{r.project_title || "untitled"}</p>
                      <p className="font-mono text-xs text-white/35">{r.project_id.slice(0, 8)}</p>
                    </div>
                  ),
                },
                { key: "bucket", header: "Bucket", render: (r) => <span className="text-xs text-white/55">{r.bucket}</span> },
                { key: "size", header: "Size", render: (r) => <span className="text-xs text-white/55">{formatBytes(r.file_size)}</span> },
                { key: "state", header: "State", render: (r) => <Badge status={r.retention_state} /> },
                {
                  key: "expires", header: "Expires", render: (r) => (
                    <span className="text-xs text-white/45">
                      {r.expires_at ? new Date(r.expires_at).toLocaleString() : "—"}
                    </span>
                  ),
                },
                {
                  key: "actions", header: "", render: (r) => canManage ? (
                    <div className="flex flex-wrap justify-end gap-1.5">
                      <button onClick={() => act(r, "extend_retention")} className="min-h-11 rounded-lg border border-white/10 px-3 py-2 text-xs text-white/65 hover:bg-white/5">Extend</button>
                      <button onClick={() => act(r, "verify_existence")} className="min-h-11 rounded-lg border border-white/10 px-3 py-2 text-xs text-white/65 hover:bg-white/5">Verify</button>
                      {r.cleanup_failed
                        ? <button onClick={() => act(r, "retry_cleanup")} className="min-h-11 rounded-lg border border-rose-400/20 px-3 py-2 text-xs text-rose-300 hover:bg-rose-400/10">Retry cleanup</button>
                        : <button onClick={() => act(r, "expire_now")} className="min-h-11 rounded-lg border border-amber-400/20 px-3 py-2 text-xs text-amber-200 hover:bg-amber-400/10">Expire</button>}
                    </div>
                  ) : null,
                  className: "text-right",
                },
              ]}
            />
            <Pagination
              page={retention.data.page}
              pageSize={retention.data.page_size}
              total={retention.data.total}
              onPage={setPage}
            />
          </>
        )}
      </section>
      <ConfirmActionDialog state={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}
