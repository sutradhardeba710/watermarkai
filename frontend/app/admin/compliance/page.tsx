"use client";
// Compliance dashboard (PRD §21). Overview cards + a triage queue of abuse
// reports. Reviewers open a report to see the full context and take legal /
// moderation actions; every action is audited server-side (§21.4/§21.6).
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import type { AbuseReportSummary } from "@/types";
import {
  Badge, DataTable, ErrorNote, LoadingBlock, PageHeader, Pagination, Stat,
} from "@/components/admin/ui";

const SEVERITIES = ["", "low", "medium", "high", "critical"];

export default function AdminCompliancePage() {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [severity, setSeverity] = useState("");
  const [page, setPage] = useState(1);

  const overview = useQuery({
    queryKey: ["admin", "compliance", "overview"],
    queryFn: () => adminApi.complianceOverview(),
  });
  const reports = useQuery({
    queryKey: ["admin", "compliance", "reports", status, severity, page],
    queryFn: () => adminApi.listComplianceReports({
      status: status || undefined, severity: severity || undefined, page, page_size: 25,
    }),
  });

  const ov = overview.data;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Compliance"
        title="Compliance & abuse"
        subtitle="Ownership confirmations, reported content, and open investigations."
      />
      {overview.error && <ErrorNote text="Unable to load compliance overview." />}
      {overview.isLoading || !ov ? (
        <LoadingBlock />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Open reviews" value={ov.open_reviews} tone={ov.open_reviews ? "border-amber-400/20 bg-amber-400/10" : undefined} />
          <Stat label="Projects reported" value={ov.projects_reported} />
          <Stat label="Repeat offenders" value={ov.repeat_offenders} />
          <Stat label="On legal hold" value={ov.projects_on_legal_hold} tone={ov.projects_on_legal_hold ? "border-rose-400/20 bg-rose-400/10" : undefined} />
          <Stat label="Ownership confirmations" value={ov.ownership_confirmations} />
          <Stat label="Suspended accounts" value={ov.suspended_accounts} />
          <Stat label="High-risk uploads" value={ov.high_risk_uploads} />
          <Stat label="Missing confirmations" value={ov.missing_confirmations} />
        </div>
      )}

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">Report queue</h2>
          <div className="flex gap-2">
            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1); }}
              className="h-10 rounded-xl border border-white/10 bg-[#10121f] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
            >
              <option value="">All statuses</option>
              <option value="new">New</option>
              <option value="under_review">Under review</option>
              <option value="waiting_for_information">Waiting for info</option>
              <option value="action_required">Action required</option>
              <option value="escalated">Escalated</option>
              <option value="legal_hold">Legal hold</option>
              <option value="resolved">Resolved</option>
              <option value="rejected">Rejected</option>
            </select>
            <select
              value={severity}
              onChange={(e) => { setSeverity(e.target.value); setPage(1); }}
              className="h-10 rounded-xl border border-white/10 bg-[#10121f] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
            >
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>{s ? s[0].toUpperCase() + s.slice(1) : "All severities"}</option>
              ))}
            </select>
          </div>
        </div>
        {reports.error && <ErrorNote text="Unable to load reports." />}
        {reports.isLoading || !reports.data ? (
          <LoadingBlock />
        ) : (
          <>
            <DataTable<AbuseReportSummary>
              rows={reports.data.items}
              rowKey={(r) => r.id}
              onRowClick={(r) => router.push(`/admin/compliance/${r.id}`)}
              empty="No reports in this view."
              columns={[
                { key: "status", header: "Status", render: (r) => <Badge status={r.status} /> },
                {
                  key: "reason", header: "Reason", render: (r) => (
                    <p className="max-w-md truncate text-sm text-white/75">{r.reason}</p>
                  ),
                },
                {
                  key: "project", header: "Project", render: (r) => (
                    <span className="font-mono text-xs text-white/40">{r.project_id?.slice(0, 8) || "—"}</span>
                  ),
                },
                {
                  key: "created", header: "Reported", render: (r) => (
                    <span className="text-xs text-white/45">{new Date(r.created_at).toLocaleDateString()}</span>
                  ),
                },
              ]}
            />
            <Pagination
              page={reports.data.page}
              pageSize={reports.data.page_size}
              total={reports.data.total}
              onPage={setPage}
            />
          </>
        )}
      </section>
    </div>
  );
}
