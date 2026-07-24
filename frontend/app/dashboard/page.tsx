"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown, CreditCard, FolderKanban, LayoutGrid, List, MoreHorizontal, Search, Upload, X, Zap } from "lucide-react";
import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { useAuthStore } from "@/features/auth/authStore";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { effectiveAdminRole } from "@/features/admin/permissions";
import { projectsApi } from "@/services/projects";
import { downloadApi } from "@/services/process";
import { paymentsApi, type CreditStatus } from "@/services/payments";
import { VideoProject } from "@/types";

const FILTERS = [{ label: "All", value: undefined }, { label: "Processing", value: "processing" }, { label: "Completed", value: "completed" }, { label: "Failed", value: "failed" }];
const statusStyles: Record<string, string> = { completed: "bg-emerald-400/15 text-emerald-300 border-emerald-400/20", processing: "bg-amber-400/15 text-amber-200 border-amber-400/20", analyzing: "bg-amber-400/15 text-amber-200 border-amber-400/20", failed: "bg-rose-400/15 text-rose-300 border-rose-400/20", uploaded: "bg-sky-400/15 text-sky-200 border-sky-400/20", created: "bg-white/10 text-white/60 border-white/10" };
function fmtDuration(s?: number) { if (!s && s !== 0) return "—"; const total = Math.round(s); return `${Math.floor(total / 60)}:${(total % 60).toString().padStart(2, "0")}`; }
function canOpen(status: string) { return ["preview_ready", "preview_processing", "processing_queued", "processing", "encoding", "completed", "failed"].includes(status); }
function prettyStatus(status: string) { return status.replaceAll("_", " ").replace(/(^| )\w/g, (m) => m.toUpperCase()); }
function StatusBadge({ status }: { status: string }) { return <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${statusStyles[status] || statusStyles.created}`}>{prettyStatus(status)}</span>; }



function DashboardPageInner() {
  useHydrateAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const user = useAuthStore((s) => s.user);
  const hydrated = useAuthStore((s) => s.hydrated);
  const ready = useAuthStore((s) => !!s.accessToken);
  const [filter, setFilter] = useState<string | undefined>();
  const [q, setQ] = useState("");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [checklist, setChecklist] = useState(true);
  const [showSubscribedToast, setShowSubscribedToast] = useState(false);

  // Wait for the store to hydrate from localStorage before deciding the user
  // is logged out — otherwise a hard reload always bounces to /login.
  useEffect(() => { if (hydrated && !ready) router.replace("/login"); }, [hydrated, ready, router]);

  // One dashboard per role: admins live in /admin (mirror of the guard in
  // app/admin/layout.tsx that bounces non-admins here).
  const isAdmin = Boolean(effectiveAdminRole(user));
  useEffect(() => { if (ready && isAdmin) router.replace("/admin"); }, [ready, isAdmin, router]);

  // Show success toast if redirected from checkout. The timer must survive the
  // effect re-run triggered by router.replace() clearing the query param, so
  // it is not cleared in the effect cleanup (only on unmount).
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (searchParams.get("subscribed") !== "1") return;
    setShowSubscribedToast(true);
    toastTimer.current = setTimeout(() => setShowSubscribedToast(false), 5000);
    // Clean URL
    router.replace("/dashboard");
  }, [searchParams, router]);
  useEffect(() => () => { if (toastTimer.current) clearTimeout(toastTimer.current); }, []);

  const query = useMemo(() => ({ status: filter, q: q || undefined }), [filter, q]);
  const { data, isLoading, isError, refetch } = useQuery({ queryKey: ["projects", query], queryFn: () => projectsApi.list(query), enabled: ready });
  const { data: credits } = useQuery<CreditStatus>({ queryKey: ["credits"], queryFn: paymentsApi.credits, enabled: ready });

  if (!ready || !user || isAdmin) return null;
  const projects = data || [];
  const completed = projects.filter((p) => p.status === "completed").length;
  const processing = projects.filter((p) => ["processing", "analyzing", "encoding"].includes(p.status)).length;

  return (
    <WorkspaceShell
      title="Projects"
      actions={
        <>
          <div className="hidden w-64 items-center rounded-xl border border-white/10 bg-white/5 px-3 transition focus-within:border-[#4f7cff]/50 focus-within:shadow-[0_0_0_3px_rgba(79,124,255,.12)] md:flex">
            <Search className="h-4 w-4 text-white/35" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search projects…" className="w-full border-0 bg-transparent px-2 py-2 text-sm text-white outline-none placeholder:text-white/30" />
          </div>
          <Link href="/upload" className="hidden items-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_8px_24px_rgba(79,124,255,.22)] transition hover:brightness-110 sm:flex"><Upload className="h-4 w-4" />New project</Link>
        </>
      }
    >
      {/* Subscribed success toast */}
      {showSubscribedToast && (
        <div className="fixed inset-x-4 bottom-[calc(5rem+env(safe-area-inset-bottom))] z-50 sm:inset-x-auto sm:bottom-6 sm:right-6 flex items-center gap-3 rounded-2xl border border-emerald-400/25 bg-[#0e1420] px-5 py-4 shadow-[0_20px_60px_rgba(52,211,153,.15)]">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-emerald-400/20 text-emerald-300">
            <Check className="h-4 w-4" />
          </span>
          <div>
            <p className="text-sm font-semibold text-white">Subscription activated!</p>
            <p className="text-xs text-white/55">Your credits have been topped up.</p>
          </div>
          <button onClick={() => setShowSubscribedToast(false)} className="ml-2 text-white/30 hover:text-white"><X className="h-4 w-4" /></button>
        </div>
      )}

      <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
          <label className="mb-5 flex min-h-12 items-center rounded-xl border border-white/10 bg-white/5 px-3 md:hidden"><Search className="h-5 w-5 shrink-0 text-white/40" /><span className="sr-only">Search projects</span><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search projects…" className="min-w-0 flex-1 border-0 bg-transparent px-3 text-base text-white outline-none placeholder:text-white/35" /></label>
          <div className="mb-8 grid gap-3 sm:grid-cols-4">
            <Stat label="Total projects" value={projects.length} icon={FolderKanban} tone="indigo" />
            <Stat label="Processing now" value={processing} icon={Zap} tone="amber" />
            <Stat label="Completed" value={completed} icon={Check} tone="emerald" />
            <Stat label="Credits today" value={credits ? `${credits.credits_remaining} / ${credits.credits_per_day}` : "—"} icon={CreditCard} tone="violet" />
          </div>
          {checklist && (
            <section className="relative mb-8 overflow-hidden rounded-2xl border border-[#4f7cff]/25 bg-gradient-to-br from-[#1a2046] via-[#141833] to-[#0e1020] p-5 shadow-[0_16px_60px_rgba(79,124,255,.1)] sm:p-6">
              <div className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-[#6d5ef7]/15 blur-3xl" />
              <button onClick={() => setChecklist(false)} aria-label="Dismiss onboarding" className="absolute right-3 top-3 z-10 grid h-11 w-11 place-items-center rounded-xl text-white/45 hover:text-white"><X className="h-4 w-4" /></button>
              <p className="bg-gradient-to-r from-[#9db9ff] to-[#c4b0ff] bg-clip-text text-xs font-semibold uppercase tracking-[.16em] text-transparent">Getting started</p>
              <h2 className="mt-2 text-lg font-semibold">A clear path from footage to final frame.</h2>
              <div className="relative mt-5 grid gap-3 sm:grid-cols-4">
                {[
                  { step: "Upload", ring: "border-[#4f7cff]/30", chip: "bg-gradient-to-br from-[#4f7cff] to-[#8b5cf6] text-white shadow-[0_4px_14px_rgba(109,94,247,.45)]" },
                  { step: "Detect / mask", ring: "border-white/[.08]", chip: "bg-[#22d3ee]/15 text-[#7de6f7]" },
                  { step: "Preview", ring: "border-white/[.08]", chip: "bg-[#a78bfa]/15 text-[#c4b0ff]" },
                  { step: "Export", ring: "border-white/[.08]", chip: "bg-[#34d399]/12 text-[#86e8c3]" },
                ].map(({ step, ring, chip }, i) => (
                  <div key={step} className={`flex items-center gap-3 rounded-xl border ${ring} bg-white/[.04] px-3 py-3 text-sm text-white/70`}>
                    <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold ${chip}`}>{i === 0 ? <Check className="h-4 w-4" /> : i + 1}</span>
                    {step}
                  </div>
                ))}
              </div>
            </section>
          )}
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div className="mobile-scroll -mx-5 flex max-w-[calc(100vw-2rem)] gap-2 overflow-x-auto px-5 sm:mx-0 sm:max-w-none sm:flex-wrap sm:px-0">{FILTERS.map((f) => <button key={f.label} onClick={() => setFilter(f.value)} className={`min-h-11 shrink-0 rounded-full border px-4 py-2 text-sm font-medium transition ${filter === f.value ? "border-[#4f7cff]/40 bg-[#4f7cff]/15 text-[#b7c7ff]" : "border-white/10 bg-white/[.03] text-white/55 hover:text-white"}`}>{f.label}</button>)}</div>
            <div className="flex items-center gap-2">
              <button onClick={() => setView("grid")} aria-label="Grid view" className={`grid h-11 w-11 place-items-center rounded-lg ${view === "grid" ? "bg-white/10 text-white" : "text-white/40"}`}><LayoutGrid className="h-4 w-4" /></button>
              <button onClick={() => setView("list")} aria-label="List view" className={`grid h-11 w-11 place-items-center rounded-lg ${view === "list" ? "bg-white/10 text-white" : "text-white/40"}`}><List className="h-4 w-4" /></button>
            </div>
          </div>
          {isError ? (
            <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 p-5 text-sm text-rose-200">We couldn’t load your projects. Please try again.</div>
          ) : isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[1,2,3].map((n) => <div key={n} className="h-72 animate-pulse rounded-2xl border border-white/10 bg-white/[.04]" />)}</div>
          ) : projects.length === 0 ? (
            <section className="relative overflow-hidden rounded-3xl border border-dashed border-[#4f7cff]/25 bg-gradient-to-b from-[#12152b] to-[#0c0e1a] px-6 py-16 text-center sm:px-12">
              <div className="pointer-events-none absolute left-1/2 top-0 h-48 w-96 -translate-x-1/2 rounded-full bg-[#4f7cff]/10 blur-3xl" />
              <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-[#4f7cff]/20 to-[#6d5ef7]/20 text-[#9eb4ff]"><Upload className="h-7 w-7" /></div>
              <h2 className="mt-6 text-2xl font-semibold">Upload your first video</h2>
              <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-white/55">Start with an authorized clip. You’ll review the detected areas, preview the cleanup, and export when it looks right.</p>
              <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
                <Link href="/upload" className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 py-3 text-sm font-semibold text-white">Upload video</Link>
                <Link href="/upload?sample=1" className="rounded-xl border border-white/10 bg-white/[.03] px-5 py-3 text-sm font-semibold text-white/75 hover:text-white">Try a sample clip</Link>
              </div>
              <p className="mt-6 text-xs text-white/35">Only upload videos you own or are licensed to edit.</p>
            </section>
          ) : (
            <div className={view === "grid" ? "grid gap-4 sm:grid-cols-2 lg:grid-cols-3" : "grid gap-3"}>
              {projects.map((p) => <ProjectCard key={p.id} project={p} onRefresh={refetch} />)}
            </div>
          )}
        </div>
    </WorkspaceShell>
  );
}

const statTones = {
  indigo: { chip: "bg-[#4f7cff]/15 text-[#9db9ff]", value: "text-white", hover: "hover:border-[#4f7cff]/35" },
  amber: { chip: "bg-amber-400/12 text-amber-200", value: "text-amber-200", hover: "hover:border-amber-400/35" },
  emerald: { chip: "bg-emerald-400/12 text-emerald-300", value: "text-emerald-300", hover: "hover:border-emerald-400/35" },
  violet: { chip: "bg-[#a78bfa]/15 text-[#c4b0ff]", value: "text-white", hover: "hover:border-[#a78bfa]/35" },
} as const;

function Stat({ label, value, icon: Icon, tone }: { label: string; value: string | number; icon: React.ComponentType<{ className?: string }>; tone: keyof typeof statTones }) {
  const t = statTones[tone];
  return (
    <div className={`flex items-center gap-4 rounded-2xl border border-white/[.08] bg-gradient-to-b from-white/[.05] to-white/[.02] p-4 transition ${t.hover}`}>
      <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${t.chip}`}><Icon className="h-5 w-5" /></span>
      <div className="min-w-0">
        <p className="truncate text-xs text-white/45">{label}</p>
        <p className={`mt-1 truncate text-2xl font-semibold ${t.value}`}>{value}</p>
      </div>
    </div>
  );
}

function ProjectCard({ project, onRefresh }: { project: VideoProject; onRefresh: () => void }) {
  const processing = ["processing", "analyzing", "encoding", "preview_processing"].includes(project.status);
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [duplicating, setDuplicating] = useState(false);

  async function duplicate() { setDuplicating(true); try { await projectsApi.duplicate(project.id); setOpen(false); onRefresh(); } catch { window.alert("This project could not be duplicated. Make sure its source upload is available."); } finally { setDuplicating(false); } }
  async function remove() { if (!window.confirm("Delete this project? This cannot be undone.")) return; setDeleting(true); try { await projectsApi.delete(project.id); onRefresh(); } catch { window.alert("This project could not be deleted. Please try again."); } finally { setDeleting(false); } }

  return (
    <article className="group overflow-hidden rounded-2xl border border-white/[.08] bg-gradient-to-b from-white/[.05] to-white/[.02] transition hover:-translate-y-0.5 hover:border-[#4f7cff]/35 hover:shadow-[0_16px_50px_rgba(79,124,255,.12)]">
      <div className="relative aspect-video overflow-hidden bg-gradient-to-br from-[#17213e] via-[#111827] to-[#251b49]">
        <div className="absolute inset-0 opacity-70 [background-image:linear-gradient(135deg,rgba(79,124,255,.18),transparent_45%),linear-gradient(315deg,rgba(34,211,238,.12),transparent_55%)]" />
        {project.thumbnail_url ? <img src={project.thumbnail_url} alt={`${project.title} thumbnail`} className="absolute inset-0 h-full w-full object-cover" /> : project.preview_url || project.proxy_url ? <video src={project.preview_url || project.proxy_url || undefined} muted playsInline preload="metadata" className="absolute inset-0 h-full w-full object-cover" /> : <div className="absolute inset-0 grid place-items-center text-white/20"><FolderKanban className="h-12 w-12" /></div>}
        <div className="absolute left-3 top-3"><StatusBadge status={project.status} /></div>
        <span className="absolute bottom-3 right-3 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white/85">{fmtDuration(project.duration)}</span>
      </div>
      <div className="p-4">
        <h3 className="line-clamp-2 min-h-12 font-medium leading-6 text-white" title={project.title}>{project.title}</h3>
        <p className="mt-1 truncate text-xs text-white/40">{project.width && project.height ? `${project.width}×${project.height}` : "Video project"} · Created {new Date(project.created_at).toLocaleDateString()}</p>
        {processing && (
          <div className="mt-3">
            <div className="flex justify-between text-[11px] text-white/45"><span>{prettyStatus(project.status)}</span><span>In progress</span></div>
            <div className="mt-1 h-1 overflow-hidden rounded-full bg-white/10"><div className="h-full w-2/3 animate-pulse rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6]" /></div>
          </div>
        )}
        <div className="mt-4 flex items-center justify-between">
          <Link href={canOpen(project.status) ? `/projects/${project.id}/result` : `/projects/${project.id}`} className="inline-flex min-h-11 items-center rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-1.5 text-sm font-medium text-white transition hover:brightness-110">Open</Link>
          <div className="relative">
            <button aria-label="More project actions" onClick={() => setOpen(!open)} className="grid h-11 w-11 place-items-center rounded-lg border border-white/10 text-white/55 hover:text-white"><MoreHorizontal className="h-5 w-5" /></button>
            {open && (
              <div className="absolute bottom-full right-0 z-20 mb-2 w-44 rounded-xl border border-white/10 bg-[#171a2b] p-1 text-sm shadow-2xl">
                <Link href={`/projects/${project.id}/candidates`} className="block rounded-lg px-3 py-2 text-white/75 hover:bg-white/10">AI Detect</Link>
                {project.status === "completed" && (
                  <button onClick={async () => { const dl = await downloadApi.issueUrl(project.id); const token = dl.url.startsWith("token:") ? dl.url.slice(6) : dl.url; window.open(downloadApi.streamUrl(project.id, token), "_blank"); }} className="block w-full rounded-lg px-3 py-2 text-left text-white/75 hover:bg-white/10">Download</button>
                )}
                <button onClick={duplicate} disabled={duplicating} className="block w-full rounded-lg px-3 py-2 text-left text-white/75 hover:bg-white/10">{duplicating ? "Duplicating..." : "Duplicate project"}</button>
                <button onClick={remove} disabled={deleting} className="block w-full rounded-lg px-3 py-2 text-left text-rose-300 hover:bg-rose-400/10">{deleting ? "Deleting…" : "Delete"}</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

// useSearchParams() requires a Suspense boundary for static prerender
// (nextjs.org/docs/messages/missing-suspense-with-csr-bailout).
export default function DashboardPage() {
  return (
    <Suspense>
      <DashboardPageInner />
    </Suspense>
  );
}
