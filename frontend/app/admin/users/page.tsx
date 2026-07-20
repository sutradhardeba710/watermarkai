"use client";
// User management list (PRD §8.1–8.2): paginated, filtered, row click → detail.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import type { AdminUser } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, PageHeader, Pagination } from "@/components/admin/ui";

export default function AdminUsersPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [plan, setPlan] = useState("");
  const [page, setPage] = useState(1);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "users", q, status, plan, page],
    queryFn: () => adminApi.listUsers({
      q: q.trim() || undefined,
      status: status || undefined,
      plan: plan || undefined,
      page,
    }),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Accounts"
        title="User management"
        subtitle="Search accounts, review usage, and control access."
      />
      <div className="flex flex-wrap gap-3">
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
          placeholder="Search name, email, or ID"
          className="h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff] sm:w-72"
        />
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="h-10 rounded-xl border border-white/10 bg-[#10121f] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
          <option value="deleted">Deleted</option>
        </select>
        <select
          value={plan}
          onChange={(e) => { setPlan(e.target.value); setPage(1); }}
          className="h-10 rounded-xl border border-white/10 bg-[#10121f] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
        >
          <option value="">All plans</option>
          <option value="free">Free</option>
          <option value="starter">Starter</option>
          <option value="pro">Pro</option>
        </select>
      </div>
      {error && <ErrorNote text="Unable to load users." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <DataTable<AdminUser>
            rows={data.items}
            rowKey={(u) => u.id}
            onRowClick={(u) => router.push(`/admin/users/${u.id}`)}
            empty="No users match this search."
            columns={[
              {
                key: "user", header: "User", render: (u) => (
                  <div className="flex items-center gap-3">
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#4f7cff]/80 to-[#6d5ef7]/80 font-semibold">
                      {(u.full_name || u.email)[0].toUpperCase()}
                    </span>
                    <div>
                      <p className="font-medium text-white">{u.full_name}</p>
                      <p className="text-xs text-white/40">{u.email}</p>
                    </div>
                  </div>
                ),
              },
              {
                key: "role", header: "Role", render: (u) => (
                  <Badge status={u.admin_role || (u.role === "admin" ? "super_admin" : "user")} />
                ),
              },
              { key: "status", header: "Status", render: (u) => <Badge status={u.account_status} /> },
              { key: "verified", header: "Verified", render: (u) => <span className="text-white/60">{u.email_verified ? "Verified" : "Pending"}</span> },
              { key: "plan", header: "Plan", render: (u) => <span className="capitalize text-white/70">{u.plan_id || "free"}</span> },
              { key: "credits", header: "Credits", render: (u) => u.credits_remaining ?? "—" },
              { key: "projects", header: "Projects", render: (u) => u.project_count },
              { key: "jobs", header: "Jobs", render: (u) => u.job_count },
            ]}
          />
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
