"use client";
// Feature flags (PRD §26.5). A simple toggle board over the canonical flag
// catalogue — the backend merges stored rows onto the full set so every flag
// always appears. Toggling requires flags.manage; viewing is config.view.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { FeatureFlag } from "@/types";
import { ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

export default function AdminFeatureFlagsPage() {
  const me = useAuthStore((s) => s.user);
  const canManage = hasPermission(me, "flags.manage");
  const qc = useQueryClient();

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "feature-flags"],
    queryFn: () => adminApi.listFeatureFlags(),
  });

  async function toggle(flag: FeatureFlag) {
    try {
      await adminApi.updateFeatureFlag(flag.key, !flag.enabled);
      toast.success(`${flag.label} ${flag.enabled ? "disabled" : "enabled"}.`);
      qc.invalidateQueries({ queryKey: ["admin", "feature-flags"] });
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Could not update flag.");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Configuration"
        title="Feature flags"
        subtitle="Turn platform capabilities on or off. Changes take effect for new requests."
      />
      {error && <ErrorNote text="Unable to load feature flags." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((flag) => (
            <div
              key={flag.key}
              className="flex items-center justify-between rounded-xl border border-white/10 bg-[#10121f] p-4"
            >
              <div className="pr-4">
                <p className="text-sm font-medium text-white/85">{flag.label}</p>
                <p className="font-mono text-xs text-white/35">{flag.key}</p>
                {flag.description && <p className="mt-1 text-xs text-white/45">{flag.description}</p>}
              </div>
              <button
                onClick={() => toggle(flag)}
                disabled={!canManage}
                aria-pressed={flag.enabled}
                className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-40 ${
                  flag.enabled ? "bg-[#4f7cff]" : "bg-white/15"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                    flag.enabled ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
