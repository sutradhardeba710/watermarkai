"use client";
// Project management list (PRD §9.1–9.3).
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import type { AdminProject } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, PageHeader, Pagination } from "@/components/admin/ui";

const STATUSES = ["", "created", "uploaded", "analyzing", "awaiting_review", "preview_ready", "processing", "completed", "failed", "cancelled", "expired"];

function formatBytes(bytes?: number | null): string {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(1)} ${units[i]}`;
}

export default function AdminProjectsPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "projects", q, status, page],
    queryFn: () => adminApi.listProjects({
      q: q.trim() || undefined,
      status: status || undefined,
      page,
    }),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Content"
        title="Projects"
        subtitle="Every uploaded video project across the platform."
      />
      <div className="flex flex-wrap gap-3">
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
          placeholder="Search title, filename, or ID"
          className="h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff] sm:w-72"
        />
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="h-10 rounded-xl border border-white/10 bg-[#10121f] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s ? s.replaceAll("_", " ") : "All statuses"}</option>
          ))}
        </select>
      </div>
      {error && <ErrorNote text="Unable to load projects." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <DataTable<AdminProject>
            rows={data.items}
            rowKey={(p) => p.id}
            onRowClick={(p) => router.push(`/admin/projects/${p.id}`)}
            empty="No projects match these filters."
            columns={[
              {
                key: "title", header: "Project", render: (p) => (
                  <div>
                    <p className="font-medium text-white">{p.title}</p>
                    <p className="text-xs text-white/40">{p.original_filename}</p>
                  </div>
                ),
              },
              { key: "user", header: "Owner", render: (p) => <span className="text-xs text-white/55">{p.user_email || p.user_id.slice(0, 8)}</span> },
              { key: "status", header: "Status", render: (p) => <Badge status={p.status} /> },
              { key: "locked", header: "Locked", render: (p) => (p.locked ? <Badge status="locked" /> : "—") },
              { key: "size", header: "Size", render: (p) => formatBytes(p.file_size) },
              {
                key: "res", header: "Resolution", render: (p) =>
                  p.width && p.height ? `${p.width}×${p.height}` : "—",
              },
              { key: "created", header: "Created", render: (p) => <span className="text-xs text-white/50">{new Date(p.created_at).toLocaleDateString()}</span> },
              { key: "expires", header: "Expires", render: (p) => <span className="text-xs text-white/50">{p.expires_at ? new Date(p.expires_at).toLocaleDateString() : "—"}</span> },
            ]}
          />
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
