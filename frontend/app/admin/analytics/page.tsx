"use client";
// Analytics & reports (PRD §24). Read-only funnel/processing/business/cost
// dashboards over a rolling window, plus §24.5 CSV/JSON exports. Viewing needs
// analytics.view; exporting needs analytics.export (server-enforced).
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Download } from "lucide-react";
import { adminApi } from "@/services/admin";
import type { ExportDataset, ExportFormat } from "@/types";
import { ErrorNote, LoadingBlock, PageHeader, Stat, formatINR } from "@/components/admin/ui";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

const WINDOWS = [7, 30, 90, 365];
const EXPORT_DATASETS: ExportDataset[] = ["users", "payments", "jobs", "audit"];

function pct(v: unknown): string {
  const n = typeof v === "number" ? v : 0;
  return `${(n * 100).toFixed(1)}%`;
}

function labelize(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AdminAnalyticsPage() {
  const me = useAuthStore((s) => s.user);
  const canExport = hasPermission(me, "analytics.export");
  const [windowDays, setWindowDays] = useState(30);
  const [exporting, setExporting] = useState<string | null>(null);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "analytics", windowDays],
    queryFn: () => adminApi.analytics(windowDays),
  });

  async function runExport(dataset: ExportDataset, format: ExportFormat) {
    setExporting(`${dataset}:${format}`);
    try {
      const blob = await adminApi.createExport(dataset, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${dataset}-export.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(`Exported ${dataset} as ${format.toUpperCase()}.`);
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Export failed.");
    } finally {
      setExporting(null);
    }
  }

  const product = (data?.product ?? {}) as Record<string, number>;
  const cost = (data?.cost ?? {}) as Record<string, number>;
  const business = (data?.business ?? {}) as Record<string, unknown>;
  const processing = (data?.processing ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Analytics"
        title="Analytics & reports"
        subtitle="Conversion funnel, processing performance, revenue and infra cost estimates."
        actions={
          <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-[#0c0e1a] p-1">
            {WINDOWS.map((w) => (
              <button
                key={w}
                onClick={() => setWindowDays(w)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  windowDays === w ? "bg-[#4f7cff] text-white" : "text-white/50 hover:text-white/80"
                }`}
              >
                {w}d
              </button>
            ))}
          </div>
        }
      />
      {error && <ErrorNote text="Unable to load analytics." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          {/* Funnel — §24.1 */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-white/70">Product funnel (§24.1)</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Registrations" value={String(product.registrations ?? 0)} />
              <Stat label="Email verification" value={pct(product.email_verification_rate)} />
              <Stat label="Upload completion" value={pct(product.upload_completion_rate)} />
              <Stat label="Analysis completion" value={pct(product.analysis_completion_rate)} />
              <Stat label="Preview generation" value={pct(product.preview_generation_rate)} />
              <Stat label="Preview → process" value={pct(product.preview_to_process_rate)} />
              <Stat label="Job success" value={pct(product.job_success_rate)} />
              <Stat label="Plan conversion" value={pct(product.plan_conversion_rate)} />
            </div>
          </section>

          {/* Business — §24.3 */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-white/70">Business (§24.3)</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="MRR" value={formatINR(Number(business.mrr_inr ?? 0))} />
              <Stat label="Active subscriptions" value={String(business.active_subscriptions ?? 0)} />
              <Stat label="Total payments" value={String(business.total_payments ?? 0)} />
              <Stat label="Total refunds" value={String(business.total_refunds ?? 0)} />
            </div>
          </section>

          {/* Cost — §24.4 */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-white/70">Infrastructure cost estimate (§24.4)</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="GPU / completed job" value={formatINR(cost.gpu_cost_per_completed_job_paise ?? 0)} />
              <Stat label="Storage / user" value={formatINR(cost.storage_cost_per_user_paise ?? 0)} />
              <Stat label="Storage / project" value={formatINR(cost.storage_cost_per_project_paise ?? 0)} />
              <Stat label="Infra / processed min" value={formatINR(cost.infra_cost_per_processed_minute_paise ?? 0)} />
            </div>
          </section>

          {/* Processing failure breakdowns — §24.2 */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-white/70">Processing performance (§24.2)</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="Avg queue (s)" value={String(processing.avg_queue_seconds ?? 0)} />
              <Stat label="Avg encoding (s)" value={String(processing.avg_encoding_seconds ?? 0)} />
              <Stat label="Sec / video min" value={String(processing.avg_processing_seconds_per_minute ?? 0)} />
              <Stat label="Credits / output" value={String(processing.credits_per_successful_output ?? 0)} />
            </div>
            <FailureTable title="Failure rate by model" map={processing.failure_rate_by_model} />
            <FailureTable title="Failure rate by worker" map={processing.failure_rate_by_worker} />
          </section>

          {/* Exports — §24.5 */}
          {canExport && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-white/70">Exports (§24.5)</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                {EXPORT_DATASETS.map((ds) => (
                  <div
                    key={ds}
                    className="flex items-center justify-between rounded-xl border border-white/10 bg-[#10121f] p-4"
                  >
                    <p className="text-sm font-medium capitalize text-white/85">{ds}</p>
                    <div className="flex gap-2">
                      {(["csv", "json"] as ExportFormat[]).map((fmt) => (
                        <button
                          key={fmt}
                          onClick={() => runExport(ds, fmt)}
                          disabled={exporting !== null}
                          className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-[#0c0e1a] px-3 py-1.5 text-xs font-medium text-white/70 transition-colors hover:text-white disabled:opacity-40"
                        >
                          <Download className="h-3.5 w-3.5" />
                          {exporting === `${ds}:${fmt}` ? "…" : fmt.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function FailureTable({ title, map }: { title: string; map: unknown }) {
  const entries = Object.entries((map as Record<string, number>) || {});
  if (entries.length === 0) return null;
  return (
    <div className="rounded-xl border border-white/10 bg-[#10121f] p-4">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-white/45">{title}</p>
      <div className="space-y-1">
        {entries.map(([key, rate]) => (
          <div key={key} className="flex items-center justify-between text-sm">
            <span className="font-mono text-white/60">{labelize(key)}</span>
            <span className={rate >= 0.05 ? "text-red-400" : "text-white/75"}>
              {(rate * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
