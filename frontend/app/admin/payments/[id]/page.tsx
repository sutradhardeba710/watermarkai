"use client";
// Payment detail + refund workflow (PRD §13.2, §13.5). Gateway identifiers are
// masked server-side. Refunds require a reason; high-value refunds are blocked
// for non-super-admins by the server (surfaced here as an error toast).
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import { Badge, ErrorNote, LoadingBlock, PageHeader, Stat, formatINR } from "@/components/admin/ui";
import { ConfirmActionDialog, ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

function Field({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-white/40">{label}</p>
      <p className={`mt-1 text-sm text-white/80 ${mono ? "font-mono" : ""}`}>{value || "—"}</p>
    </div>
  );
}

export default function AdminPaymentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const me = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const [dialog, setDialog] = useState<ConfirmActionState | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "payment", id],
    queryFn: () => adminApi.getPayment(id),
  });

  const canManage = hasPermission(me, "billing.manage");

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "payment", id] });
    qc.invalidateQueries({ queryKey: ["admin", "payments"] });
  }

  function openRefund() {
    if (!data) return;
    setDialog({
      title: "Issue a refund",
      description: `Refundable balance: ${formatINR(data.refundable_inr)}. Enter the amount in ₹ (rupees) and a reason. High-value refunds require super-admin approval.`,
      confirmLabel: "Issue refund",
      danger: true,
      requireReason: true,
      numberLabel: "Refund amount (₹)",
      numberDefault: Math.round(data.refundable_inr / 100),
      onConfirm: async (reason, amountRupees) => {
        const amount_inr = Math.round((amountRupees ?? 0) * 100);
        try {
          await adminApi.refundPayment(id, { amount_inr, reason });
          toast.success("Refund issued.");
          refresh();
        } catch (err) {
          toast.error((err as { message?: string })?.message || "Refund failed.");
          throw err;
        }
      },
    });
  }

  async function saveNote(manualReview?: boolean) {
    try {
      await adminApi.updatePaymentNote(id, {
        internal_note: note ?? undefined,
        manual_review: manualReview,
      });
      toast.success("Payment updated.");
      setNote(null);
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Update failed.");
    }
  }

  return (
    <div className="space-y-6">
      <button onClick={() => router.push("/admin/payments")} className="text-sm text-white/50 hover:text-white">
        ← Back to payments
      </button>
      {error && <ErrorNote text="Unable to load payment." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <PageHeader
            eyebrow="Payment"
            title={formatINR(data.amount_inr)}
            subtitle={data.user_email || data.user_id}
            actions={
              canManage && data.refundable_inr > 0 ? (
                <button
                  onClick={openRefund}
                  className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-2 text-sm font-semibold text-rose-200 hover:bg-rose-500/20"
                >
                  Refund
                </button>
              ) : null
            }
          />

          <div className="flex flex-wrap items-center gap-3">
            <Badge status={data.status} />
            {data.refund_status && data.refund_status !== "none" && <Badge status={`refund_${data.refund_status}`} />}
            {data.manual_review && <Badge status="review" />}
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Amount" value={formatINR(data.amount_inr)} />
            <Stat label="Discount" value={formatINR(data.discount_inr)} />
            <Stat label="Tax" value={formatINR(data.tax_inr)} />
            <Stat label="Refunded" value={formatINR(data.refunded_inr)} />
          </div>

          <div className="grid gap-6 rounded-2xl border border-white/10 bg-[#10121f] p-6 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Payment ID" value={data.razorpay_payment_id} mono />
            <Field label="Order ID" value={data.razorpay_order_id} mono />
            <Field label="Subscription" value={data.razorpay_subscription_id} mono />
            <Field label="Method" value={data.method} />
            <Field label="Plan" value={data.plan_id} />
            <Field label="Promo" value={data.promo_code} />
            <Field label="Credits issued" value={String(data.credits_issued)} />
            <Field label="Captured at" value={data.captured_at ? new Date(data.captured_at).toLocaleString() : null} />
            <Field label="Created" value={new Date(data.created_at).toLocaleString()} />
            {data.failure_reason && <Field label="Failure reason" value={data.failure_reason} />}
          </div>

          {/* Refund history */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">Refunds</h2>
            {data.refunds.length === 0 ? (
              <p className="text-sm text-white/45">No refunds issued.</p>
            ) : (
              <div className="divide-y divide-white/10 rounded-2xl border border-white/10 bg-[#10121f]">
                {data.refunds.map((r) => (
                  <div key={r.id} className="flex items-center justify-between px-4 py-3">
                    <div>
                      <p className="text-sm text-white/80">{formatINR(r.amount_inr)} · {r.kind}</p>
                      <p className="text-xs text-white/40">{r.reason || "—"}</p>
                    </div>
                    <div className="text-right">
                      <Badge status={r.status} />
                      <p className="mt-1 text-xs text-white/40">{new Date(r.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Internal note + manual review (PRD §13.2) */}
          {canManage && (
            <section className="space-y-3 rounded-2xl border border-white/10 bg-[#10121f] p-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">Internal note</h2>
              <textarea
                value={note ?? data.internal_note ?? ""}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                placeholder="Add an internal note (visible to admins only)."
                className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff]"
              />
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => saveNote(undefined)}
                  className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-2 text-sm font-semibold text-white"
                >
                  Save note
                </button>
                <button
                  onClick={() => saveNote(!data.manual_review)}
                  className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white/70 hover:bg-white/5"
                >
                  {data.manual_review ? "Clear manual review" : "Flag for manual review"}
                </button>
              </div>
            </section>
          )}
        </>
      )}
      <ConfirmActionDialog state={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}
