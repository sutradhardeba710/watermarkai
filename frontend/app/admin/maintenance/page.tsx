"use client";
// Maintenance mode (PRD §26.6). Configure a maintenance window, the public
// message shown to users, and which operations stay live while it is active.
// Viewing is config.view; saving requires maintenance.manage.
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { MaintenanceState } from "@/types";
import { ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

const TOGGLES: { key: keyof MaintenanceState; label: string; hint: string }[] = [
  { key: "maintenance_enabled", label: "Maintenance mode enabled", hint: "Master switch — gates the platform for non-admins." },
  { key: "allow_administrators", label: "Allow administrators", hint: "Admins keep access while maintenance is on." },
  { key: "allow_existing_jobs_to_finish", label: "Let existing jobs finish", hint: "In-flight processing jobs run to completion." },
  { key: "pause_new_uploads", label: "Pause new uploads", hint: "Block new video uploads." },
  { key: "pause_new_processing_jobs", label: "Pause new processing jobs", hint: "Block starting new processing runs." },
  { key: "disable_checkout", label: "Disable checkout", hint: "Block new payments / plan purchases." },
];

export default function AdminMaintenancePage() {
  const me = useAuthStore((s) => s.user);
  const canManage = hasPermission(me, "maintenance.manage");
  const [state, setState] = useState<MaintenanceState | null>(null);
  const [busy, setBusy] = useState(false);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "maintenance"],
    queryFn: () => adminApi.getMaintenance(),
  });

  useEffect(() => {
    if (data) setState(data);
  }, [data]);

  async function save() {
    if (!state) return;
    setBusy(true);
    try {
      const saved = await adminApi.updateMaintenance(state);
      setState(saved);
      toast.success("Maintenance settings saved.");
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Could not save settings.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operations"
        title="Maintenance mode"
        subtitle="Schedule a maintenance window and control what stays available while it runs."
      />
      {error && <ErrorNote text="Unable to load maintenance settings." />}
      {isLoading || !state ? (
        <LoadingBlock />
      ) : (
        <>
          {state.maintenance_enabled && (
            <div className="rounded-xl border border-amber-400/25 bg-amber-400/10 p-3 text-sm text-amber-100">
              Maintenance mode is currently <strong>ON</strong>.
            </div>
          )}

          <section className="space-y-3 rounded-2xl border border-white/10 bg-[#10121f] p-5">
            {TOGGLES.map((t) => (
              <div key={t.key} className="flex items-center justify-between border-b border-white/5 py-2 last:border-0">
                <div className="pr-4">
                  <p className="text-sm text-white/85">{t.label}</p>
                  <p className="text-xs text-white/40">{t.hint}</p>
                </div>
                <button
                  onClick={() => setState({ ...state, [t.key]: !state[t.key] })}
                  disabled={!canManage}
                  aria-pressed={Boolean(state[t.key])}
                  className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-40 ${
                    state[t.key] ? "bg-[#4f7cff]" : "bg-white/15"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                      state[t.key] ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
            ))}
          </section>

          <section className="grid gap-4 rounded-2xl border border-white/10 bg-[#10121f] p-5 sm:grid-cols-2">
            <label className="block text-sm text-white/75 sm:col-span-2">
              Public message
              <textarea
                value={state.public_message}
                onChange={(e) => setState({ ...state, public_message: e.target.value })}
                disabled={!canManage}
                rows={2}
                placeholder="We’ll be back shortly…"
                className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff]"
              />
            </label>
            <label className="block text-sm text-white/75">
              Status page link
              <input
                value={state.status_page_link || ""}
                onChange={(e) => setState({ ...state, status_page_link: e.target.value })}
                disabled={!canManage}
                placeholder="https://status.example.com"
                className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff]"
              />
            </label>
          </section>

          {canManage && (
            <button
              onClick={save}
              disabled={busy}
              className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {busy ? "Saving..." : "Save maintenance settings"}
            </button>
          )}
        </>
      )}
    </div>
  );
}
