"use client";
// Admin Overview (PRD §7). Legacy `?tab=X` deep links redirect to /admin/X.
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import { ErrorNote, LoadingBlock, PageHeader, Stat } from "@/components/admin/ui";

const TAB_ROUTES: Record<string, string> = {
  jobs: "/admin/jobs",
  workers: "/admin/workers",
  users: "/admin/users",
  audit: "/admin/audit",
  abuse: "/admin/abuse",
  settings: "/admin/settings",
};

function formatINR(paise?: number | null): string {
  if (!paise) return "₹0";
  return `₹${(paise / 100).toLocaleString("en-IN")}`;
}

export default function AdminOverviewPage() {
  const router = useRouter();

  useEffect(() => {
    // Legacy deep links: /admin?tab=X → /admin/X.
    const tab = new URLSearchParams(window.location.search).get("tab");
    if (tab && TAB_ROUTES[tab]) router.replace(TAB_ROUTES[tab]);
  }, [router]);

  const { data: d, error } = useQuery({ queryKey: ["admin", "overview"], queryFn: adminApi.overview, refetchInterval: 30_000 });

  if (error) return <ErrorNote text="Unable to load system overview." />;
  if (!d) return <LoadingBlock />;

  const stalled = d.gpu_workers === 0 && d.queue_length > 0;
  const successRate = d.success_rate == null ? "—" : `${Math.round(d.success_rate * 100)}%`;

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="Admin control center"
        subtitle="Business activity and system health at a glance."
      />
      {stalled && (
        <div role="alert" className="mt-6 flex gap-3 rounded-2xl border border-amber-400/30 bg-amber-400/10 p-5 text-amber-100">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
          <div>
            <p className="font-semibold">No active workers — jobs are stalling in the queue</p>
            <p className="mt-1 text-sm text-amber-100/70">
              There are {d.queue_length} queued jobs and no GPU workers reporting online. Check the Workers page or restart Celery.
            </p>
          </div>
        </div>
      )}

      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/40">Business</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Total users" value={d.total_users} />
          <Stat label="New today" value={d.users_today ?? "—"} hint={`${d.users_this_month ?? 0} this month`} />
          <Stat label="Active subscriptions" value={d.active_subscriptions ?? 0} />
          <Stat label="Revenue this month" value={formatINR(d.revenue_this_month_inr)} />
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/40">Processing</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label="Queue length"
            value={d.queue_length}
            tone={d.queue_length > 0 ? "border-amber-400/30 bg-amber-400/10" : undefined}
          />
          <Stat label="Projects today" value={d.projects_today ?? 0} />
          <Stat label="Completed today" value={d.jobs_completed_today ?? 0} tone="border-emerald-400/20 bg-emerald-400/10" />
          <Stat
            label="Failed today"
            value={d.jobs_failed_today ?? 0}
            tone={(d.jobs_failed_today ?? 0) > 0 ? "border-rose-400/25 bg-rose-400/10" : undefined}
          />
          <Stat label="Success rate (today)" value={successRate} />
          <Stat label="Avg processing" value={d.avg_processing_seconds ? `${d.avg_processing_seconds.toFixed(1)}s` : "—"} />
          <Stat
            label="GPU workers"
            value={d.gpu_workers}
            tone={d.gpu_workers === 0 ? "border-rose-400/25 bg-rose-400/10" : undefined}
          />
          <Stat label="Storage" value={`${(d.storage_bytes / 1073741824).toFixed(1)} GB`} />
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/40">Accounts</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Active users" value={d.active_users} />
          <Stat
            label="Suspended"
            value={d.suspended_users}
            tone={d.suspended_users > 0 ? "border-rose-400/25 bg-rose-400/10" : undefined}
          />
          <Stat label="All-time completed" value={d.completed_jobs} />
          <Stat label="All-time failed" value={d.failed_jobs} />
        </div>
      </section>
    </div>
  );
}
