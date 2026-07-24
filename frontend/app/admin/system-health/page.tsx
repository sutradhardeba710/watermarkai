"use client";
// System health board (PRD §25). Live service up/down grid + threshold-scored
// metrics, plus an incident timeline with ack/silence/resolve actions. Viewing
// needs health.view; incident actions need health.manage (server-enforced).
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { Incident, IncidentAction, HealthMetric, ServiceStatus } from "@/types";
import { ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

const SERVICE_DOT: Record<string, string> = {
  operational: "bg-emerald-400",
  down: "bg-red-400",
  unknown: "bg-white/25",
};
const METRIC_TONE: Record<string, string> = {
  ok: "text-emerald-400",
  warn: "text-amber-400",
  critical: "text-red-400",
  unknown: "text-white/40",
};
const OVERALL_TONE: Record<string, string> = {
  operational: "text-emerald-400",
  degraded: "text-amber-400",
  critical: "text-red-400",
};

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AdminSystemHealthPage() {
  const me = useAuthStore((s) => s.user);
  const canManage = hasPermission(me, "health.manage");
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "system-health"],
    queryFn: () => adminApi.systemHealth(),
    refetchInterval: 30_000,
  });
  const incidents = useQuery({
    queryKey: ["admin", "incidents"],
    queryFn: () => adminApi.listIncidents(),
  });

  async function act(inc: Incident, action: IncidentAction) {
    let note: string | undefined;
    if (action === "resolve" || action === "add_note") {
      note = window.prompt(`Note for "${action}"`) || undefined;
      if (!note) {
        toast.error("A note is required for this action.");
        return;
      }
    }
    setBusy(`${inc.id}:${action}`);
    try {
      await adminApi.actOnIncident(inc.id, { action, note });
      toast.success(`Incident ${action}d.`);
      qc.invalidateQueries({ queryKey: ["admin", "incidents"] });
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Action failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operations"
        title="System health"
        subtitle={
          data
            ? `Live dependency probes and rolling metrics · checked ${new Date(data.checked_at).toLocaleTimeString()}`
            : "Live dependency probes, rolling metrics and the incident timeline."
        }
        actions={
          data && (
            <span className={`text-sm font-semibold ${OVERALL_TONE[data.overall] || "text-white/60"}`}>
              {labelize(data.overall)}
            </span>
          )
        }
      />
      {error && <ErrorNote text="Unable to load system health." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-white/70">Services (§25.1)</h2>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {data.services.map((s: ServiceStatus) => (
                <div
                  key={s.name}
                  title={s.detail || undefined}
                  className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-[#10121f] px-4 py-3"
                >
                  <span>
                    <span className="block text-sm text-white/80">{labelize(s.name)}</span>
                    {s.detail && <span className="mt-0.5 block text-[10px] text-white/35">{s.detail}</span>}
                  </span>
                  <span className="flex items-center gap-2 text-xs text-white/50">
                    <span className={`h-2.5 w-2.5 rounded-full ${SERVICE_DOT[s.status]}`} />
                    {s.status}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-white/70">Metrics (§25.2)</h2>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {data.metrics.map((m: HealthMetric) => (
                <div
                  key={m.metric}
                  className="flex items-center justify-between rounded-xl border border-white/10 bg-[#10121f] px-4 py-3"
                >
                  <span className="text-sm text-white/70">{labelize(m.metric)}</span>
                  <span className={`text-sm font-medium ${METRIC_TONE[m.status]}`}>
                    {m.value ?? "—"}{m.value != null && m.unit ? ` ${m.unit}` : ""}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-white/70">Incidents (§25.3)</h2>
            {incidents.isLoading ? (
              <LoadingBlock />
            ) : !incidents.data || incidents.data.length === 0 ? (
              <p className="rounded-xl border border-white/10 bg-[#10121f] p-4 text-sm text-white/45">
                No incidents recorded.
              </p>
            ) : (
              <div className="space-y-2">
                {incidents.data.map((inc) => (
                  <div key={inc.id} className="rounded-xl border border-white/10 bg-[#10121f] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium text-white/85">{inc.title}</p>
                        <p className="text-xs text-white/40">
                          {labelize(inc.service)} · {inc.severity} · {inc.status}
                        </p>
                      </div>
                      {canManage && inc.status !== "resolved" && (
                        <div className="flex flex-wrap gap-2">
                          {(["acknowledge", "silence", "add_note", "resolve"] as IncidentAction[]).map((a) => (
                            <button
                              key={a}
                              onClick={() => act(inc, a)}
                              disabled={busy !== null}
                              className="rounded-lg border border-white/10 bg-[#0c0e1a] px-2.5 py-1 text-xs text-white/70 transition-colors hover:text-white disabled:opacity-40"
                            >
                              {busy === `${inc.id}:${a}` ? "…" : labelize(a)}
                            </button>
                          ))}
                        </div>
                      )}
                      {canManage && inc.status === "resolved" && (
                        <button
                          onClick={() => act(inc, "reopen")}
                          disabled={busy !== null}
                          className="rounded-lg border border-white/10 bg-[#0c0e1a] px-2.5 py-1 text-xs text-white/70 transition-colors hover:text-white disabled:opacity-40"
                        >
                          Reopen
                        </button>
                      )}
                    </div>
                    {inc.detail && <p className="mt-2 text-xs text-white/50">{inc.detail}</p>}
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
