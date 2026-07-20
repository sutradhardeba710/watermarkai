"use client";
// Audit log (ADMIN-006 / PRD §27): filters + pagination + expandable rows
// showing previous/new values, reason, and request context.
import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import type { AuditEntry } from "@/types";
import { Badge, ErrorNote, LoadingBlock, PageHeader, Pagination } from "@/components/admin/ui";

const TARGET_TYPES = ["", "user", "project", "job", "abuse_report", "system_settings"];

export default function AdminAuditPage() {
  const [action, setAction] = useState("");
  const [targetType, setTargetType] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "audit", action, targetType, page],
    queryFn: () => adminApi.listAudit({
      action: action || undefined,
      target_type: targetType || undefined,
      page,
    }),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Traceability"
        title="Audit log"
        subtitle="Permanent record of administrative and security-sensitive actions."
      />
      <div className="flex flex-wrap gap-3">
        <input
          value={action}
          onChange={(e) => { setAction(e.target.value); setPage(1); }}
          placeholder="Filter by action (e.g. user.suspend)"
          className="h-10 w-64 rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff]"
        />
        <select
          value={targetType}
          onChange={(e) => { setTargetType(e.target.value); setPage(1); }}
          className="h-10 rounded-xl border border-white/10 bg-[#10121f] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
        >
          {TARGET_TYPES.map((t) => (
            <option key={t} value={t}>{t ? t.replaceAll("_", " ") : "All targets"}</option>
          ))}
        </select>
      </div>
      {error && <ErrorNote text="Unable to load the audit log." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#10121f]">
            <table className="min-w-full text-sm">
              <thead className="bg-[#0c0e1a] text-left text-xs uppercase tracking-wide text-white/40">
                <tr>
                  <th className="px-4 py-3">Time</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Target</th>
                  <th className="px-4 py-3">Result</th>
                  <th className="px-4 py-3">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {data.items.map((entry: AuditEntry) => (
                  <Fragment key={entry.id}>
                    <tr
                      onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}
                      className="cursor-pointer hover:bg-white/[.025]"
                    >
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-white/50">{new Date(entry.created_at).toLocaleString()}</td>
                      <td className="px-4 py-3"><Badge status={entry.action} /></td>
                      <td className="px-4 py-3 font-mono text-xs text-white/55">{entry.actor_id?.slice(0, 8) || "System"}</td>
                      <td className="px-4 py-3 text-xs text-white/55">{entry.target_type || "—"} {entry.target_id?.slice(0, 8) || ""}</td>
                      <td className="px-4 py-3"><Badge status={entry.result || "success"} /></td>
                      <td className="max-w-xs truncate px-4 py-3 text-xs text-white/45">{entry.reason || "—"}</td>
                    </tr>
                    {expanded === entry.id && (
                      <tr className="bg-[#0c0e1a]/60">
                        <td colSpan={6} className="px-6 py-4">
                          <div className="grid gap-4 text-xs sm:grid-cols-2">
                            {entry.previous_data && (
                              <div>
                                <p className="font-semibold uppercase tracking-wide text-white/40">Previous</p>
                                <pre className="mt-1 overflow-x-auto rounded-lg bg-black/30 p-3 font-mono text-rose-200/80">{JSON.stringify(entry.previous_data, null, 2)}</pre>
                              </div>
                            )}
                            {entry.new_data && (
                              <div>
                                <p className="font-semibold uppercase tracking-wide text-white/40">New</p>
                                <pre className="mt-1 overflow-x-auto rounded-lg bg-black/30 p-3 font-mono text-emerald-200/80">{JSON.stringify(entry.new_data, null, 2)}</pre>
                              </div>
                            )}
                            {entry.details && (
                              <div>
                                <p className="font-semibold uppercase tracking-wide text-white/40">Details</p>
                                <pre className="mt-1 overflow-x-auto rounded-lg bg-black/30 p-3 font-mono text-white/60">{JSON.stringify(entry.details, null, 2)}</pre>
                              </div>
                            )}
                            <div className="space-y-1 text-white/45">
                              <p className="font-semibold uppercase tracking-wide text-white/40">Request context</p>
                              <p>Request ID: <span className="font-mono">{entry.request_id || "—"}</span></p>
                              <p>IP hash: <span className="font-mono">{entry.ip_hash?.slice(0, 16) || "—"}</span></p>
                              <p className="max-w-md truncate">Agent: {entry.user_agent || "—"}</p>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            {data.items.length === 0 && <p className="p-8 text-center text-sm text-white/45">No audit events match these filters.</p>}
          </div>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
