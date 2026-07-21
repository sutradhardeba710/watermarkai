import type { PublicPlan } from "@/services/payments";

export type PricingPlan = {
  id: "free" | "starter" | "pro"; name: string; price: number; annualPrice?: number | null; promoPrice?: number; promoLabel?: string; billingInterval: string;
  creditsPerDay: number; description: string; features: string[]; speed: string; batch: string; retention: string; support: string;
  maxUploadMb: number | null; maxDurationSeconds: number | null; maxResolution: string | null; concurrentJobs: number | null;
  storageAllowanceMb: number | null; processingModes: string; popular?: boolean;
};

export const currencySymbol = "₹";
export const creditsPerJob = 100;
export const creditPolicy = {
  resetCopy: "Daily credits reset on the scheduled cycle and do not roll over.",
  previewCopy: "Quick previews are free.",
  fullJobCopy: "Full processing costs 100 credits per job.",
  failureCopy: "Failed jobs return the 100-credit job cost through the credit ledger.",
};

const platformDefaults = { maxUploadMb: 500, maxDurationSeconds: 300, maxResolution: "1920 × 1080", concurrentJobs: null, storageAllowanceMb: null, retention: "7-day output default", processingModes: "Fast · Balanced · High Quality" };

export const pricingPlans: PricingPlan[] = [
  { id: "free", name: "Free", price: 0, annualPrice: null, billingInterval: "monthly", creditsPerDay: 500, description: "Try the complete detect, mask, preview, and processing workflow on authorized footage.", features: ["AI-assisted detection", "Manual mask controls", "Free quick previews", "Signed result download"], speed: "Standard queue", batch: "Single project flow", support: "Help Center", ...platformDefaults },
  { id: "starter", name: "Starter", price: 4099, annualPrice: null, billingInterval: "monthly", creditsPerDay: 1000, description: "More daily capacity and priority processing for regular editing work.", features: ["Everything in Free", "Priority processing", "Live plan limits", "Email support"], speed: "Priority queue", batch: "Single project flow", support: "Email support", popular: true, ...platformDefaults },
  { id: "pro", name: "Pro", price: 16799, annualPrice: null, billingInterval: "monthly", creditsPerDay: 2000, description: "The largest daily allowance and fastest configured processing lane.", features: ["Everything in Starter", "Fastest configured lane", "Plan-managed concurrency", "Priority support"], speed: "Fastest configured queue", batch: "Plan-managed", support: "Priority support", ...platformDefaults },
];

export const jobsPerDay = (plan: PricingPlan) => Math.floor(plan.creditsPerDay / creditsPerJob);
export const videosPerDay = jobsPerDay;

export function mergeLivePlans(live: PublicPlan[]): PricingPlan[] {
  if (!live.length) return pricingPlans;
  const statics = new Map(pricingPlans.map((plan) => [plan.id, plan]));
  return live.slice().sort((a, b) => a.display_order - b.display_order || a.price_inr - b.price_inr).map((row) => {
    const id = row.id as PricingPlan["id"];
    const base = statics.get(id) ?? pricingPlans[0];
    return {
      ...base,
      id,
      name: row.name || base.name,
      price: Math.round(row.price_inr / 100),
      annualPrice: row.annual_price_inr === null ? null : Math.round(row.annual_price_inr / 100),
      billingInterval: row.billing_interval || base.billingInterval,
      creditsPerDay: row.credits_per_day,
      description: row.description || base.description,
      retention: row.retention_days ? `${row.retention_days}-day retention` : base.retention,
      support: row.support_level || base.support,
      maxUploadMb: row.max_upload_mb ?? base.maxUploadMb,
      maxDurationSeconds: row.max_duration_seconds ?? base.maxDurationSeconds,
      maxResolution: row.max_resolution ?? base.maxResolution,
      concurrentJobs: row.concurrent_jobs ?? base.concurrentJobs,
      storageAllowanceMb: row.storage_allowance_mb ?? base.storageAllowanceMb,
      popular: row.is_recommended || base.popular,
    };
  });
}
