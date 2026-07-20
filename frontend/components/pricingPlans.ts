export type PricingPlan = {
  id: "free" | "starter" | "pro";
  name: string;
  price: number;
  promoPrice?: number;
  promoLabel?: string;
  creditsPerDay: number;
  description: string;
  features: string[];
  speed: string;
  batch: string;
  retention: string;
  support: string;
  popular?: boolean;
};

export const currencySymbol = "\u20B9";
export const creditsPerVideo = 100;
export const creditPolicy = { resetCopy: "Credits reset every 24 hours and do not roll over.", unitCopy: "100 credits = 1 video" };
export const pricingPlans: PricingPlan[] = [
  { id: "free", name: "Free", price: 0, creditsPerDay: 500, description: "Everything you need to try ClearFrame on authorized footage.", features: ["Authorized video cleanup", "AI detection + manual mask control", "Before/after preview & review", "Original audio, resolution, and frame rate preserved"], speed: "Standard", batch: "Single videos", retention: "Standard retention", support: "Community", },
  { id: "starter", name: "Starter", price: 4099, creditsPerDay: 1000, description: "More daily capacity and priority processing for regular work.", features: ["Everything in Free", "Priority processing", "Longer retention", "Email support"], speed: "Priority", batch: "Single videos", retention: "Longer retention", support: "Email support", popular: true },
  { id: "pro", name: "Pro", price: 16799, creditsPerDay: 2000, description: "The fastest lane for high-volume, repeatable cleanup.", features: ["Everything in Starter", "Fastest processing lane", "Batch processing", "Priority support", "Batch processing controls"], speed: "Fastest", batch: "Batch processing", retention: "Configurable", support: "Priority support" },
];
export const videosPerDay = (plan: PricingPlan) => plan.creditsPerDay / creditsPerVideo;

import type { PublicPlan } from "@/services/payments";

/**
 * Merge live plan rows from GET /plans over the static presentation defaults.
 * Prices/credits/name come from the DB (admin-editable); features, copy, and
 * promo labels stay from the static config until they're modeled server-side.
 * Backend stores paise; UI shows rupees.
 */
export function mergeLivePlans(live: PublicPlan[]): PricingPlan[] {
  if (!live.length) return pricingPlans;
  const statics = new Map(pricingPlans.map((p) => [p.id, p]));
  return live
    .slice()
    .sort((a, b) => a.display_order - b.display_order || a.price_inr - b.price_inr)
    .map((row) => {
      const base = statics.get(row.id as PricingPlan["id"]);
      return {
        id: (row.id as PricingPlan["id"]) ?? "free",
        name: row.name || base?.name || row.id,
        price: Math.round(row.price_inr / 100),
        promoPrice: base?.promoPrice,
        promoLabel: base?.promoLabel,
        creditsPerDay: row.credits_per_day,
        description: row.description || base?.description || "",
        features: base?.features ?? [],
        speed: base?.speed ?? "Standard",
        batch: base?.batch ?? "Single videos",
        retention: row.retention_days ? `${row.retention_days}-day retention` : base?.retention ?? "Standard retention",
        support: row.support_level || base?.support || "Community",
        popular: row.is_recommended || base?.popular,
      };
    });
}