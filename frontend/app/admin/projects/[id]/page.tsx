"use client";
// Project detail (PRD §9.4–9.5): metadata, jobs, outputs, compliance, notes,
// moderation actions (retention / expire / lock / delete files / delete).
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AdminProjectAction } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock } from "@/components/admin/ui";
import { ConfirmActionDialog, ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

function formatBytes(bytes?: number | null): string {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(1)} ${units[i]}`;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-white/40">{label}</p>
      <p className="mt-1 text-sm text-white/80">{value}</p>
    </div>
  );
}

export default function AdminProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const me = useAuthStore((s) => s.user);
  const canManage = hasPermission(me, "projects.manage");
  const qc = useQueryClient();
  const [dialog, setDialog] = useState<ConfirmActionState | null>(null);

  const { data: p, error, isLoading } = useQuery({
    queryKey: ["admin", "project", id],
    queryFn: () => adminApi.getProject(id),
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "project", id] });
  }

  function act(action: AdminProjectAction, opts: {
    title: string; description: string; danger?: boolean;
    requireReason?: boolean; numberLabel?: string; numberDefault?: number;
  }) {
    setDialog({
      title: opts.title,
      description: opts.description,
      confirmLabel: opts.title,
      danger: opts.danger,
      requireReason: opts.requireReason,
      numberLabel: opts.numberLabel,
      numberDefault: opts.numberDefault,
      onConfirm: async (reason, amount) => {
        await adminApi.actOnProject(id, action, {
          reason: reason || undefined,
          hours: action === "extend_retention" ? amount : undefined,
        });
        toast.success(`${opts.title} — done.`);
        refresh();
      },
    });
  }

  if (error) return <ErrorNote text="Unable to load this project." />;
  if (isLoading || !p) return <LoadingBlock />;

  return (
    <div className="space-y-6">
      <button onClick={() => router.push("/admin/projects")} className="text-sm text-[#9eb4ff] hover:text-white">← All projects</button>

      <section className="rounded-2xl border border-white/10 bg-[#10121f] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">{p.title}</h1>
            <p className="mt-1 text-sm text-white/50">{p.original_filename}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge status={p.status} />
              {p.locked && <Badge status="locked" />}
              {p.deleted && <Badge status="deleted" />}
              <button
                onClick={() => router.push(`/admin/users/${p.user_id}`)}
                className="text-xs text-[#9eb4ff] hover:text-white"
              >
                {p.user_email || p.user_id.slice(0, 8)} →
              </button>
            </div>
            {p.moderation_note && (
              <p className="mt-3 rounded-xl border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
                Moderation note: {p.moderation_note}
              </p>
            )}
          </div>
          {canManage && !p.deleted && (
            <div className="flex flex-wrap gap-2">
              <button onClick={() => act("extend_retention", { title: "Extend retention", description: "Push the expiry date forward by the given number of hours.", numberLabel: "Hours", numberDefault: 168 })} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/70 hover:bg-white/5">Extend retention</button>
              <button onClick={() => act("expire_now", { title: "Expire now", description: "Files become eligible for cleanup immediately.", danger: true, requireReason: true })} className="rounded-lg border border-amber-400/20 px-3 py-1.5 text-xs text-amber-200 hover:bg-amber-400/10">Expire now</button>
              {p.locked ? (
                <button onClick={() => act("unlock", { title: "Unlock project", description: "Processing and downloads are allowed again." })} className="rounded-lg border border-emerald-400/20 px-3 py-1.5 text-xs text-emerald-300 hover:bg-emerald-400/10">Unlock</button>
              ) : (
                <button onClick={() => act("lock", { title: "Lock project", description: "Blocks processing and downloads pending review. The reason is stored as a moderation note.", danger: true, requireReason: true })} className="rounded-lg border border-rose-400/20 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-400/10">Lock</button>
              )}
              <button onClick={() => act("delete_files", { title: "Delete files", description: "Best-effort deletion of all stored artifacts (source, proxy, preview, output, thumbnail). The project row remains for traceability.", danger: true, requireReason: true })} className="rounded-lg border border-rose-400/20 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-400/10">Delete files</button>
              <button
                onClick={() => setDialog({
                  title: "Delete project",
                  description: "Soft delete: files are removed and the project is hidden from the user. Compliance records are retained. This cannot be undone from the panel.",
                  confirmLabel: "Delete project",
                  danger: true,
                  requireReason: true,
                  onConfirm: async (reason) => {
                    await adminApi.deleteProject(id, reason);
                    toast.success("Project deleted.");
                    router.push("/admin/projects");
                  },
                })}
                className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-1.5 text-xs font-semibold text-rose-300 hover:bg-rose-500/20"
              >
                Delete project
              </button>
            </div>
          )}
        </div>
        <div className="mt-5 grid gap-4 border-t border-white/[.07] pt-4 sm:grid-cols-3 lg:grid-cols-6">
          <Field label="Duration" value={p.duration ? `${p.duration.toFixed(1)}s` : "—"} />
          <Field label="Resolution" value={p.width && p.height ? `${p.width}×${p.height}` : "—"} />
          <Field label="FPS" value={p.fps ?? "—"} />
          <Field label="Size" value={formatBytes(p.file_size)} />
          <Field label="Codec" value={p.video_codec || "—"} />
          <Field label="Audio" value={p.has_audio ? p.audio_codec || "yes" : "none"} />
          <Field label="Created" value={new Date(p.created_at).toLocaleString()} />
          <Field label="Completed" value={p.completed_at ? new Date(p.completed_at).toLocaleString() : "—"} />
          <Field label="Expires" value={p.expires_at ? new Date(p.expires_at).toLocaleString() : "—"} />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/40">Jobs</h2>
        <DataTable
          rows={p.jobs}
          rowKey={(j) => j.id}
          empty="No jobs for this project."
          columns={[
            { key: "id", header: "Job", render: (j) => <span className="font-mono text-xs">{j.id.slice(0, 8)}</span> },
            { key: "type", header: "Type", render: (j) => j.job_type },
            { key: "status", header: "Status", render: (j) => <Badge status={j.status} /> },
            { key: "progress", header: "Progress", render: (j) => `${j.progress}%` },
            { key: "worker", header: "Worker", render: (j) => <span className="text-xs text-white/55">{j.worker_id || "—"}</span> },
            { key: "error", header: "Error", render: (j) => <span className="text-xs text-rose-300">{j.error_code || "—"}</span> },
            { key: "created", header: "Created", render: (j) => <span className="text-xs text-white/50">{new Date(j.created_at).toLocaleString()}</span> },
          ]}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/40">Output files</h2>
        <DataTable
          rows={p.outputs}
          rowKey={(o) => o.id}
          empty="No output files."
          columns={[
            { key: "key", header: "Storage key", render: (o) => <span className="max-w-xs truncate font-mono text-xs text-white/55">{o.storage_key}</span> },
            { key: "bucket", header: "Bucket", render: (o) => o.bucket },
            { key: "size", header: "Size", render: (o) => formatBytes(o.file_size) },
            { key: "quality", header: "Quality", render: (o) => o.quality_mode },
            { key: "expires", header: "Expires", render: (o) => <span className="text-xs text-white/50">{o.expires_at ? new Date(o.expires_at).toLocaleString() : "—"}</span> },
          ]}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-white/40">Compliance confirmations</h2>
        {p.compliance.length === 0 ? (
          <p className="rounded-2xl border border-rose-400/20 bg-rose-500/[.06] p-4 text-sm text-rose-200">
            No ownership confirmation recorded for this project.
          </p>
        ) : (
          <DataTable
            rows={p.compliance}
            rowKey={(c) => c.id}
            columns={[
              { key: "version", header: "Version", render: (c) => c.confirmation_version },
              { key: "time", header: "Confirmed", render: (c) => new Date(c.confirmed_at).toLocaleString() },
              { key: "ip", header: "IP hash", render: (c) => <span className="font-mono text-xs text-white/50">{c.ip_hash?.slice(0, 16) || "—"}</span> },
            ]}
          />
        )}
      </section>

      {p.notes.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-white/40">Notes</h2>
          {p.notes.map((n) => (
            <article key={n.id} className="rounded-2xl border border-white/10 bg-[#10121f] p-4">
              <p className="text-sm leading-6 text-white/75">{n.body}</p>
              <p className="mt-2 text-xs text-white/35">By {n.author_id.slice(0, 8)} · {new Date(n.created_at).toLocaleString()}</p>
            </article>
          ))}
        </section>
      )}

      <ConfirmActionDialog state={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}
