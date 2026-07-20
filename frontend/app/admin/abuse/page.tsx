"use client";
// Abuse reports (ADMIN-007 / PRD §21).
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AbuseAction, AbuseReportSummary } from "@/types";
import { Badge, ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";
import { ConfirmActionDialog, ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

export default function AdminAbusePage() {
  const user = useAuthStore((s) => s.user);
  const canManage = hasPermission(user, "abuse.manage");
  const [filter, setFilter] = useState("");
  const [dialog, setDialog] = useState<ConfirmActionState | null>(null);
  const qc = useQueryClient();

  const { data: reports, error, isLoading } = useQuery({
    queryKey: ["admin", "abuse", filter],
    queryFn: () => adminApi.listAbuse(filter || undefined),
  });

  function act(report: AbuseReportSummary, action: AbuseAction) {
    const labels: Record<AbuseAction, string> = {
      dismiss: "Dismiss report",
      escalate: "Escalate report",
      suspend_reporter: "Suspend reporter",
    };
    setDialog({
      title: labels[action],
      description:
        action === "suspend_reporter"
          ? "The reporter's account will be suspended immediately and their sessions revoked."
          : `Mark report ${report.id.slice(0, 8)}… as ${action === "dismiss" ? "dismissed" : "escalated"}.`,
      confirmLabel: labels[action],
      danger: action === "suspend_reporter",
      onConfirm: async () => {
        await adminApi.actOnAbuse(report.id, action);
        toast.success("Report updated.");
        qc.invalidateQueries({ queryKey: ["admin", "abuse"] });
      },
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Compliance"
        title="Abuse reports"
        subtitle="Review reports, escalate investigations, and protect the platform."
        actions={
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="h-10 rounded-xl border border-white/10 bg-[#10121f] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="escalated">Escalated</option>
            <option value="dismissed">Dismissed</option>
            <option value="actioned">Actioned</option>
          </select>
        }
      />
      {error && <ErrorNote text="Unable to load abuse reports." />}
      {isLoading ? (
        <LoadingBlock />
      ) : (
        <div className="space-y-3">
          {(reports || []).map((report) => (
            <article key={report.id} className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Badge status={report.status} />
                    <span className="font-mono text-xs text-white/35">{report.id.slice(0, 8)}</span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-white/75">{report.reason}</p>
                  <p className="mt-2 text-xs text-white/40">
                    Project {report.project_id?.slice(0, 8) || "unknown"} · Reporter {report.reported_by?.slice(0, 8) || "anonymous"} · {new Date(report.created_at).toLocaleString()}
                  </p>
                </div>
                {report.status === "open" && canManage && (
                  <div className="flex flex-wrap gap-2">
                    <button onClick={() => act(report, "dismiss")} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/65 hover:bg-white/5">Dismiss</button>
                    <button onClick={() => act(report, "escalate")} className="rounded-lg border border-amber-400/20 px-3 py-1.5 text-xs text-amber-200 hover:bg-amber-400/10">Escalate</button>
                    {report.reported_by && (
                      <button onClick={() => act(report, "suspend_reporter")} className="rounded-lg border border-rose-400/20 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-400/10">Suspend reporter</button>
                    )}
                  </div>
                )}
              </div>
            </article>
          ))}
          {(reports || []).length === 0 && (
            <p className="rounded-2xl border border-white/10 bg-[#10121f] p-8 text-center text-sm text-white/45">No abuse reports in this view.</p>
          )}
        </div>
      )}
      <ConfirmActionDialog state={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}
