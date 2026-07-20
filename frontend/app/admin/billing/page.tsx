"use client";
// Billing dashboard (PRD §13.1). Revenue, MRR, ARPU, subscription + payment
// health. Amounts arrive in paise from the API.
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/services/admin";
import { ErrorNote, LoadingBlock, PageHeader, Stat, formatINR } from "@/components/admin/ui";

export default function AdminBillingPage() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "billing"],
    queryFn: () => adminApi.billingOverview(),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Finance"
        title="Billing"
        subtitle="Revenue, recurring income, and payment health across the platform."
      />
      {error && <ErrorNote text="Unable to load billing overview." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Revenue today" value={formatINR(data.revenue_today_inr)} />
            <Stat label="Revenue this month" value={formatINR(data.revenue_month_inr)} />
            <Stat label="MRR" value={formatINR(data.mrr_inr)} hint="Monthly recurring revenue" />
            <Stat label="ARPU" value={formatINR(data.arpu_inr)} hint="Per active subscription" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Active subscriptions" value={data.active_subscriptions} />
            <Stat label="New this month" value={data.new_subscriptions} />
            <Stat label="Renewals" value={data.renewals} />
            <Stat label="Cancellations" value={data.cancellations} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Stat
              label="Failed payments (month)"
              value={data.failed_payments}
              tone={data.failed_payments > 0 ? "border-amber-400/20 bg-amber-400/10" : undefined}
            />
            <Stat label="Refunds issued (month)" value={formatINR(data.refunds_inr)} />
          </div>
        </>
      )}
    </div>
  );
}
