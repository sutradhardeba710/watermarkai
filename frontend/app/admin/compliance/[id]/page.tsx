"use client";
// Compliance report detail (PRD §21.4, §21.5). Shows the report + its project /
// owner / reporter context and offers the full set of legal & moderation
// actions. Sensitive video is NOT auto-previewed — reviewers act on
// metadata/reason first (§21.4/§21.6). Every action is audited server-side.
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AbuseSeverity, ComplianceAction } from "@/types";
import { Badge, ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";
import { ConfirmActionDialog, ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

function Field({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-white/40">{label}</p>
      <p className={`mt-1 text-sm text-white/80 ${mono ? "font-mono" : ""}`}>{value || "—"}</p>
    </div>
  );
}

const ACTIONS: { action: ComplianceAction; label: string; danger?: boolean; reason?: boolean }[] = [
  { action: "mark_safe", label: "Mark safe" },
  { action: "request_information", label: "Request info" },
  { action: "restrict_processing", label: "Restrict processing" },
  { action: "disable_downloads", label: "Disable downloads" },
  { action: "escalate", label: "Escalate" },
  { action: "add_note", label: "Add note", reason: true },
  { action: "place_legal_hold", label: "Place legal hold", danger: true, reason: true },
  { action: "remove_legal_hold", label: "Remove legal hold", reason: true },
  { action: "suspend_account", label: "Suspend account", danger: true, reason: true },
  { action: "ban_account", label: "Ban account", danger: true, reason: true },
  { action: "close", label: "Close report" },
];

const SEVERITIES: AbuseSeverity[] = ["low", "medium", "high", "critical"];

export default function AdminComplianceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const me = useAuthStore((s) => s.user);
  const canManage = hasPermission(me, "abuse.manage");
  const qc = useQueryClient();
  const [dialog, setDialog] = useState<ConfirmActionState | null>(null);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "compliance", id],
    queryFn: () => adminApi.getComplianceReport(id),
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "compliance"] });
  }

  function act(a: (typeof ACTIONS)[number]) {
    if (!data) return;
    setDialog({
      title: a.label,
      description: `${a.label} for report ${data.id.slice(0, 8)}…${data.project_title ? ` (project “${data.project_title}”)` : ""}.`,
      confirmLabel: a.label,
      danger: a.danger,
      requireReason: a.reason,
      onConfirm: async (reason) => {
        const res = await adminApi.actOnCompliance(data.id, { action: a.action, reason: reason || undefined });
        toast.success(`Report ${res.status.replaceAll("_", " ")}.`);
        refresh();
      },
    });
  }

  async function changeSeverity(sev: AbuseSeverity) {
    if (!data) return;
    try {
      await adminApi.setReportSeverity(data.id, sev);
      toast.success(`Severity set to ${sev}.`);
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Could not update severity.");
    }
  }

  return (
    <div className="space-y-6">
      <button onClick={() => router.push("/admin/compliance")} className="text-sm text-white/50 hover:text-white/80">
        ← Back to compliance
      </button>
      {error && <ErrorNote text="Unable to load this report." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <PageHeader
            eyebrow="Compliance"
            title={`Report ${data.id.slice(0, 8)}`}
            subtitle={data.project_title || undefined}
            actions={
              <div className="flex items-center gap-2">
                <Badge status={data.status} />
                <Badge status={data.severity} />
              </div>
            }
          />

          {(data.legal_hold || data.processing_restricted || data.downloads_disabled) && (
            <div className="flex flex-wrap gap-2">
              {data.legal_hold && <Badge status="legal_hold" />}
              {data.processing_restricted && <Badge status="processing_restricted" />}
              {data.downloads_disabled && <Badge status="downloads_disabled" />}
            </div>
          )}

          <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
            <p className="text-xs uppercase tracking-wide text-white/40">Reason</p>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-white/80">{data.reason}</p>
            {data.legal_hold_reason && (
              <p className="mt-3 rounded-lg border border-rose-400/20 bg-rose-400/5 p-3 text-xs text-rose-200">
                Legal hold: {data.legal_hold_reason}
              </p>
            )}
            {data.resolution_note && (
              <p className="mt-3 rounded-lg border border-white/10 bg-white/[.03] p-3 text-xs text-white/60">
                Note: {data.resolution_note}
              </p>
            )}
          </section>

          <section className="grid gap-4 rounded-2xl border border-white/10 bg-[#10121f] p-5 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Project" value={data.project_id} mono />
            <Field label="Owner" value={data.project_owner_email} />
            <Field label="Reporter" value={data.reporter_email || data.reported_by} />
            <Field label="Assigned reviewer" value={data.assigned_reviewer} mono />
            <Field label="Prior reports on project" value={String(data.previous_reports)} />
            <Field label="Reported" value={new Date(data.created_at).toLocaleString()} />
          </section>

          {canManage ? (
            <>
              <section className="space-y-3">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">Severity</h2>
                <div className="flex flex-wrap gap-2">
                  {SEVERITIES.map((s) => (
                    <button
                      key={s}
                      onClick={() => changeSeverity(s)}
                      disabled={data.severity === s}
                      className={`rounded-lg border px-3 py-1.5 text-xs capitalize ${
                        data.severity === s
                          ? "border-[#4f7cff]/40 bg-[#4f7cff]/15 text-white"
                          : "border-white/10 text-white/60 hover:bg-white/5"
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </section>

              <section className="space-y-3">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">Actions</h2>
                <div className="flex flex-wrap gap-2">
                  {ACTIONS.map((a) => (
                    <button
                      key={a.action}
                      onClick={() => act(a)}
                      className={`rounded-lg border px-3 py-1.5 text-xs ${
                        a.danger
                          ? "border-rose-400/20 text-rose-300 hover:bg-rose-400/10"
                          : "border-white/10 text-white/65 hover:bg-white/5"
                      }`}
                    >
                      {a.label}
                    </button>
                  ))}
                </div>
              </section>
            </>
          ) : (
            <p className="text-sm text-white/40">You have read-only access to compliance reports.</p>
          )}
        </>
      )}
      <ConfirmActionDialog state={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}
