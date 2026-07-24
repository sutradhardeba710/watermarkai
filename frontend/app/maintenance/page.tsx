"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowUpRight, Clock3, RefreshCw, ShieldCheck, Wrench } from "lucide-react";

type MaintenanceStatus = {
  maintenance_enabled: boolean;
  public_message: string;
  end_time: string | null;
  status_page_link: string | null;
};

function formatTime(value: string | null) {
  if (!value) return "We’ll share an update as soon as service is restored.";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "We’ll share an update as soon as service is restored."
    : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** Public maintenance page. It checks the unauthenticated health endpoint and
 * returns visitors to the site automatically as soon as the window ends. */
export default function MaintenancePage() {
  const [status, setStatus] = useState<MaintenanceStatus | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let timer: number | undefined;
    let cancelled = false;
    const check = async () => {
      try {
        const res = await fetch("/health/maintenance", { cache: "no-store" });
        if (!res.ok) throw new Error("Maintenance status is unavailable");
        const data: MaintenanceStatus = await res.json();
        if (cancelled) return;
        setStatus(data);
        setLastChecked(new Date());
        if (!data.maintenance_enabled) {
          window.location.replace("/");
          return;
        }
      } catch {
        // Keep the page available if the API itself is being restarted.
      } finally {
        if (!cancelled) setRefreshing(false);
      }
      if (!cancelled) timer = window.setTimeout(check, 15000);
    };
    void check();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, []);

  const message = status?.public_message || "We’re carrying out scheduled work to keep ClearFrame reliable and secure.";
  const expectedTime = useMemo(() => formatTime(status?.end_time ?? null), [status?.end_time]);

  function refreshNow() {
    setRefreshing(true);
    window.location.reload();
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#07080f] px-5 py-6 text-white sm:px-8">
      <div aria-hidden="true" className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(79,124,255,.18),transparent_34%),radial-gradient(circle_at_15%_90%,rgba(109,94,247,.11),transparent_30%)]" />
      <div className="relative mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-5xl flex-col">
        <header className="flex items-center justify-between">
          <div aria-label="ClearFrame" className="inline-flex items-center gap-3 px-2 py-2 text-sm font-semibold tracking-tight">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#5d7cff] to-[#6d5ef7] shadow-lg shadow-[#4f7cff]/20"><Wrench className="h-4 w-4" /></span>
            ClearFrame
          </div>
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-300/15 bg-amber-300/10 px-3 py-1.5 text-xs font-medium text-amber-100">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-300" /> Scheduled maintenance
          </span>
        </header>

        <section className="mx-auto flex w-full max-w-2xl flex-1 items-center py-12 sm:py-16">
          <div className="w-full rounded-3xl border border-white/10 bg-[#10121f]/85 p-6 shadow-2xl shadow-black/25 backdrop-blur sm:p-10">
            <div className="grid h-14 w-14 place-items-center rounded-2xl border border-[#89a2ff]/25 bg-[#4f7cff]/10 text-[#aabaff]"><Activity className="h-6 w-6" /></div>
            <p className="mt-7 text-sm font-medium text-[#aabaff]">Service update</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">We’ll be right back.</h1>
            <p className="mt-4 max-w-xl text-base leading-7 text-white/65">{message}</p>

            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/8 bg-black/15 p-4">
                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[.12em] text-white/40"><Clock3 className="h-3.5 w-3.5" /> Expected update</div>
                <p className="mt-2 text-sm font-medium leading-6 text-white/85">{expectedTime}</p>
              </div>
              <div className="rounded-2xl border border-white/8 bg-black/15 p-4">
                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[.12em] text-white/40"><ShieldCheck className="h-3.5 w-3.5" /> Your work</div>
                <p className="mt-2 text-sm font-medium leading-6 text-white/85">Saved projects and completed exports remain protected.</p>
              </div>
            </div>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <button type="button" onClick={refreshNow} disabled={refreshing} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-[#11131e] transition hover:bg-white/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 disabled:cursor-wait disabled:opacity-70">
                <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} /> Check again
              </button>
              {status?.status_page_link && (
                <a href={status.status_page_link} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/10 px-4 py-2.5 text-sm font-medium text-white/75 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8ea8ff]">
                  View service status <ArrowUpRight className="h-4 w-4" />
                </a>
              )}
            </div>
            <p aria-live="polite" className="mt-6 text-xs text-white/35">{lastChecked ? `Last checked ${lastChecked.toLocaleTimeString()}.` : "Checking service status…"} We’ll return you automatically when service is restored.</p>
          </div>
        </section>

        <footer className="pb-2 text-center text-xs text-white/30">ClearFrame · Authorized video cleanup</footer>
      </div>
    </main>
  );
}