"use client";
// Credit ledger dashboard (PRD §17.1). Read-only snapshot of today's credit
// flow plus users running low. Balances are never modified here — adjustments go
// through the ledger elsewhere (PRD §17.4).
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import type { AdminUser } from "@/types";
import { DataTable, ErrorNote, LoadingBlock, PageHeader, Stat } from "@/components/admin/ui";

export default function AdminCreditsPage() {
  const router = useRouter();
  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "credits"],
    queryFn: () => adminApi.creditDashboard(),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Finance"
        title="Credits"
        subtitle="Today's credit issuance and consumption, plus low-balance accounts."
      />
      {error && <ErrorNote text="Unable to load credit dashboard." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Issued today" value={data.credits_issued_today} />
            <Stat label="Consumed today" value={data.credits_consumed_today} />
            <Stat label="Refunded today" value={data.credits_refunded_today} />
            <Stat label="Bonus today" value={data.bonus_credits_today} />
          </div>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">Low-balance users</h2>
            <DataTable<AdminUser>
              rows={data.low_balance_users}
              rowKey={(u) => u.id}
              onRowClick={(u) => router.push(`/admin/users/${u.id}`)}
              empty="No users are running low on credits."
              columns={[
                {
                  key: "user", header: "User", render: (u) => (
                    <div>
                      <p className="text-sm text-white/80">{u.full_name || u.email}</p>
                      <p className="text-xs text-white/40">{u.email}</p>
                    </div>
                  ),
                },
                { key: "plan", header: "Plan", render: (u) => <span className="text-xs text-white/55">{u.plan_id || "free"}</span> },
                {
                  key: "credits", header: "Credits", render: (u) => (
                    <span className="text-amber-200">{u.credits_remaining ?? 0}</span>
                  ),
                },
                { key: "jobs", header: "Jobs", render: (u) => u.job_count },
              ]}
            />
          </section>
        </>
      )}
    </div>
  );
}
