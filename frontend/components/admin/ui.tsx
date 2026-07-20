// Shared admin UI primitives — extracted from the original single-page
// admin panel so all /admin/* routes render consistently.
"use client";
import { ReactNode } from "react";

export function Badge({ status }: { status: string }) {
  const tone =
    status.includes("fail") || status.includes("cancel") || status === "suspended" || status === "banned" || status === "deleted" || status === "critical" || status === "debit"
      ? "border-rose-400/20 bg-rose-400/15 text-rose-300"
      : status.includes("process") || status.includes("queue") || status.includes("pending") || status === "escalated" || status === "past_due"
        ? "border-amber-400/20 bg-amber-400/15 text-amber-200"
        : status === "completed" || status === "online" || status === "active" || status === "captured" || status === "credit" || status === "success"
          ? "border-emerald-400/20 bg-emerald-400/15 text-emerald-300"
          : "border-white/10 bg-white/5 text-white/60";
  return (
    <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${tone}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function Stat({ label, value, tone, hint }: { label: string; value: string | number; tone?: string; hint?: string }) {
  return (
    <div className={`rounded-2xl border p-4 ${tone || "border-white/10 bg-[#10121f]"}`}>
      <p className="text-xs uppercase tracking-wide text-white/45">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
      {hint && <p className="mt-1 text-xs text-white/35">{hint}</p>}
    </div>
  );
}

export function LoadingBlock() {
  return <div className="h-32 animate-pulse rounded-2xl border border-white/10 bg-white/[.04]" />;
}

/** Format an amount stored in paise as ₹ (PRD §13 — prices persisted ×100). */
export function formatINR(paise?: number | null): string {
  if (paise == null) return "—";
  return `₹${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

export function ErrorNote({ text }: { text: string }) {
  return <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 p-5 text-sm text-rose-200">{text}</div>;
}

export function PageHeader({ eyebrow, title, subtitle, actions }: {
  eyebrow?: string; title: string; subtitle?: string; actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="text-xs uppercase tracking-[.16em] text-white/35">{eyebrow}</p>}
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-2 text-sm text-white/50">{subtitle}</p>}
      </div>
      {actions}
    </header>
  );
}

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
}

export function DataTable<T>({ columns, rows, rowKey, onRowClick, empty }: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  empty?: string;
}) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-white/10 bg-[#10121f]">
      <table className="min-w-full text-sm">
        <thead className="bg-[#0c0e1a] text-left text-xs uppercase tracking-wide text-white/40">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={`px-4 py-3 ${c.className || ""}`}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/10">
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`hover:bg-white/[.03] ${onRowClick ? "cursor-pointer" : ""}`}
            >
              {columns.map((c) => (
                <td key={c.key} className={`px-4 py-3 ${c.className || ""}`}>{c.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && (
        <p className="p-8 text-center text-sm text-white/45">{empty || "No results."}</p>
      )}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }: {
  page: number; pageSize: number; total: number; onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between text-sm text-white/50">
      <span>
        Page {page} of {pages} · {total} total
      </span>
      <div className="flex gap-2">
        <button
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-40"
        >
          Previous
        </button>
        <button
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
          className="rounded-lg border border-white/10 px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}
