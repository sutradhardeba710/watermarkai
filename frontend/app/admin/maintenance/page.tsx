"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarClock, CircleAlert, ExternalLink, ShieldCheck, Wrench } from "lucide-react";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { MaintenanceState } from "@/types";
import { ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

function toLocalInput(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function fromLocalInput(value: string) {
  return value ? new Date(value).toISOString() : null;
}

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

  const scheduleSummary = useMemo(() => {
    if (!state?.maintenance_enabled) return "Maintenance is off. Visitors can use the platform normally.";
    if (state.start_time && new Date(state.start_time) > new Date()) return `Scheduled to start ${new Date(state.start_time).toLocaleString()}.`;
    if (state.end_time) return `Active now. The public page will clear after ${new Date(state.end_time).toLocaleString()}.`;
    return "Active now until you turn it off.";
  }, [state]);

  async function save() {
    if (!state) return;
    if (state.start_time && state.end_time && new Date(state.end_time) <= new Date(state.start_time)) {
      toast.error("The end time must be later than the start time.");
      return;
    }
    setBusy(true);
    try {
      const saved = await adminApi.updateMaintenance(state);
      setState(saved);
      toast.success("Maintenance settings saved and applied.");
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Could not save maintenance settings.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Operations" title="Maintenance mode" subtitle="Plan a controlled maintenance window and keep visitors clearly informed." />
      {error && <ErrorNote text="Unable to load maintenance settings." />}
      {isLoading || !state ? <LoadingBlock /> : (
        <>
          <section className={`rounded-2xl border p-5 ${state.maintenance_enabled ? "border-amber-400/25 bg-amber-400/[.08]" : "border-emerald-400/20 bg-emerald-400/[.06]"}`}>
            <div className="flex gap-3">
              {state.maintenance_enabled ? <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" /> : <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-300" />}
              <div>
                <p className="text-sm font-semibold text-white">{state.maintenance_enabled ? "Maintenance is enabled" : "Platform is available"}</p>
                <p className="mt-1 text-sm text-white/60">{scheduleSummary}</p>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5 sm:p-6">
            <div className="flex flex-col gap-3 border-b border-white/8 pb-5 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="font-semibold text-white">Access policy</h2>
                <p className="mt-1 max-w-2xl text-sm leading-6 text-white/50">When enabled, the public API returns a maintenance response and visitors are directed to the status page. Existing worker jobs are allowed to finish; administrators can remain available for recovery.</p>
              </div>
              <span className="inline-flex w-fit items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/60"><Wrench className="h-3.5 w-3.5" /> Full platform gate</span>
            </div>
            <div className="mt-5 space-y-4">
              <ToggleRow label="Enable maintenance mode" hint="Turns on the public maintenance page at the selected time." checked={state.maintenance_enabled} disabled={!canManage} onChange={() => setState({ ...state, maintenance_enabled: !state.maintenance_enabled })} />
              <ToggleRow label="Allow administrators" hint="Keeps the admin area available while the public platform is paused." checked={state.allow_administrators} disabled={!canManage} onChange={() => setState({ ...state, allow_administrators: !state.allow_administrators })} />
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5 sm:p-6">
            <div className="flex items-center gap-2"><CalendarClock className="h-5 w-5 text-[#9eb4ff]" /><h2 className="font-semibold text-white">Schedule</h2></div>
            <p className="mt-1 text-sm text-white/50">Leave both times blank to start immediately and keep maintenance on until you switch it off.</p>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="block text-sm text-white/75">Start time
                <input type="datetime-local" value={toLocalInput(state.start_time)} onChange={(e) => setState({ ...state, start_time: fromLocalInput(e.target.value) })} disabled={!canManage} className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff] disabled:opacity-50" />
              </label>
              <label className="block text-sm text-white/75">Expected end time
                <input type="datetime-local" value={toLocalInput(state.end_time)} onChange={(e) => setState({ ...state, end_time: fromLocalInput(e.target.value) })} disabled={!canManage} className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff] disabled:opacity-50" />
              </label>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5 sm:p-6">
            <h2 className="font-semibold text-white">Visitor communication</h2>
            <p className="mt-1 text-sm text-white/50">This content appears on the public maintenance page.</p>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="block text-sm text-white/75 sm:col-span-2">Public message
                <textarea value={state.public_message} onChange={(e) => setState({ ...state, public_message: e.target.value })} disabled={!canManage} rows={3} maxLength={500} placeholder="We’re performing scheduled work and will be back shortly." className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff] disabled:opacity-50" />
              </label>
              <label className="block text-sm text-white/75 sm:col-span-2">Status page link <span className="text-white/35">(optional)</span>
                <div className="relative mt-2"><input type="url" value={state.status_page_link || ""} onChange={(e) => setState({ ...state, status_page_link: e.target.value || null })} disabled={!canManage} placeholder="https://status.example.com" className="h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 pr-10 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff] disabled:opacity-50" /> <ExternalLink className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-white/35" /></div>
              </label>
            </div>
          </section>

          {canManage && <button onClick={save} disabled={busy} className="inline-flex min-h-11 items-center justify-center rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-wait disabled:opacity-50">{busy ? "Saving…" : "Save maintenance settings"}</button>}
        </>
      )}
    </div>
  );
}

function ToggleRow({ label, hint, checked, disabled, onChange }: { label: string; hint: string; checked: boolean; disabled: boolean; onChange: () => void }) {
  return <div className="flex items-center justify-between gap-4"><div><p className="text-sm font-medium text-white/85">{label}</p><p className="mt-1 text-xs leading-5 text-white/40">{hint}</p></div><button type="button" onClick={onChange} disabled={disabled} aria-pressed={checked} className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8ea8ff] disabled:opacity-40 ${checked ? "bg-[#4f7cff]" : "bg-white/15"}`}><span className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform ${checked ? "translate-x-6" : "translate-x-1"}`} /></button></div>;
}