"use client";
// Payments list (PRD §13.3). Gateway IDs arrive already masked from the server.
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import type { PaymentListItem } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, PageHeader, Pagination, formatINR } from "@/components/admin/ui";

const STATUSES = ["", "created", "authorized", "captured", "failed", "refunded", "partially_refunded", "disputed", "sandbox"];

export default function AdminPaymentsPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "payments", q, status, page],
    queryFn: () => adminApi.listPayments({ q: q.trim() || undefined, status: status || undefined, page }),
  });

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Finance" title="Payments" subtitle="Every payment recorded from Razorpay and sandbox flows." />
      <div className="flex flex-wrap gap-3">
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
          placeholder="Search payment / order ID or email"
          className="h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff] sm:w-80"
        />
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="h-10 rounded-xl border border-white/10 bg-[#10121f] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
        >
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replaceAll("_", " ") : "All statuses"}</option>)}
        </select>
      </div>
      {error && <ErrorNote text="Unable to load payments." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <DataTable<PaymentListItem>
            rows={data.items}
            rowKey={(p) => p.id}
            onRowClick={(p) => router.push(`/admin/payments/${p.id}`)}
            empty="No payments match these filters."
            columns={[
              {
                key: "id", header: "Payment", render: (p) => (
                  <div>
                    <p className="font-mono text-xs text-white/70">{p.razorpay_payment_id || p.id.slice(0, 12)}</p>
                    <p className="text-xs text-white/40">{p.user_email || p.user_id.slice(0, 8)}</p>
                  </div>
                ),
              },
              { key: "amount", header: "Amount", render: (p) => <span className="font-medium text-white">{formatINR(p.amount_inr)}</span> },
              { key: "status", header: "Status", render: (p) => <Badge status={p.status} /> },
              { key: "plan", header: "Plan", render: (p) => <span className="text-xs text-white/55">{p.plan_id || "—"}</span> },
              { key: "promo", header: "Promo", render: (p) => <span className="text-xs text-white/55">{p.promo_code || "—"}</span> },
              {
                key: "refund", header: "Refunded", render: (p) =>
                  p.refunded_inr > 0 ? <span className="text-xs text-amber-200">{formatINR(p.refunded_inr)}</span> : "—",
              },
              { key: "flag", header: "", render: (p) => (p.manual_review ? <Badge status="review" /> : null) },
              { key: "created", header: "Date", render: (p) => <span className="text-xs text-white/50">{new Date(p.created_at).toLocaleDateString()}</span> },
            ]}
          />
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
