"use client";
// Subscriptions list + lifecycle actions (PRD §14). Cancel/resume/reactivate
// and plan changes route through the server which writes the audit trail.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AdminSubscriptionListItem, SubscriptionAction } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, PageHeader, Pagination } from "@/components/admin/ui";
import { ConfirmActionDialog, ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

const STATUSES = ["", "trialing", "active", "paused", "past_due", "pending", "cancelled", "expired", "completed"];

export default function AdminSubscriptionsPage() {
  const me = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<ConfirmActionState | null>(null);

  const canManage = hasPermission(me, "billing.manage");
  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "subscriptions", status, page],
    queryFn: () => adminApi.listSubscriptions({ status: status || undefined, page }),
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "subscriptions"] });
  }

  async function run(sub: AdminSubscriptionListItem, action: SubscriptionAction, reason?: string, plan_id?: string) {
    try {
      await adminApi.actOnSubscription(sub.id, { action, reason, plan_id });
      toast.success("Subscription updated.");
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Action failed.");
      throw err;
    }
  }

  function confirmCancel(sub: AdminSubscriptionListItem) {
    setDialog({
      title: "Cancel subscription",
      description: `Immediately cancel the subscription for ${sub.user_email || sub.user_id}. This stops future renewals.`,
      confirmLabel: "Cancel subscription",
      danger: true,
      requireReason: true,
      onConfirm: (reason) => run(sub, "cancel", reason),
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Finance" title="Subscriptions" subtitle="Active and past subscriptions with lifecycle controls." />
      <div className="flex flex-wrap gap-3">
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="h-10 rounded-xl border border-white/10 bg-[#10121f] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
        >
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replaceAll("_", " ") : "All statuses"}</option>)}
        </select>
      </div>
      {error && <ErrorNote text="Unable to load subscriptions." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <DataTable<AdminSubscriptionListItem>
            rows={data.items}
            rowKey={(s) => s.id}
            empty="No subscriptions match these filters."
            columns={[
              {
                key: "user", header: "User", render: (s) => (
                  <div>
                    <p className="text-sm text-white/80">{s.user_email || s.user_id.slice(0, 8)}</p>
                    <p className="text-xs text-white/40">{s.plan_id}</p>
                  </div>
                ),
              },
              {
                key: "status", header: "Status", render: (s) => (
                  <div className="flex flex-wrap gap-1">
                    <Badge status={s.display_status} />
                    {s.cancel_at_period_end && <Badge status="ending" />}
                  </div>
                ),
              },
              { key: "failures", header: "Fails", render: (s) => (s.payment_failures > 0 ? <span className="text-amber-200">{s.payment_failures}</span> : "—") },
              { key: "period", header: "Renews", render: (s) => <span className="text-xs text-white/50">{s.current_period_end ? new Date(s.current_period_end).toLocaleDateString() : "—"}</span> },
              { key: "created", header: "Since", render: (s) => <span className="text-xs text-white/50">{new Date(s.created_at).toLocaleDateString()}</span> },
              {
                key: "actions", header: "", className: "text-right", render: (s) =>
                  canManage ? (
                    <div className="flex justify-end gap-2">
                      {["active", "trialing", "past_due", "paused"].includes(s.status) && (
                        <button
                          onClick={() => confirmCancel(s)}
                          className="rounded-lg border border-rose-400/30 px-2.5 py-1 text-xs text-rose-200 hover:bg-rose-500/10"
                        >
                          Cancel
                        </button>
                      )}
                      {["cancelled", "expired", "paused"].includes(s.status) && (
                        <button
                          onClick={() => run(s, "reactivate")}
                          className="rounded-lg border border-white/10 px-2.5 py-1 text-xs text-white/70 hover:bg-white/5"
                        >
                          Reactivate
                        </button>
                      )}
                      {s.cancel_at_period_end && s.status === "active" && (
                        <button
                          onClick={() => run(s, "resume")}
                          className="rounded-lg border border-white/10 px-2.5 py-1 text-xs text-white/70 hover:bg-white/5"
                        >
                          Resume
                        </button>
                      )}
                    </div>
                  ) : null,
              },
            ]}
          />
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
        </>
      )}
      <ConfirmActionDialog state={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}
