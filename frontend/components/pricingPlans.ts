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
  { id: "starter", name: "Starter", price: 4099, promoPrice: 199, promoLabel: "First month offer", creditsPerDay: 1000, description: "More daily capacity and priority processing for regular work.", features: ["Everything in Free", "Priority processing", "Longer retention", "Email support"], speed: "Priority", batch: "Single videos", retention: "Longer retention", support: "Email support", popular: true },
  { id: "pro", name: "Pro", price: 16799, promoPrice: 499, promoLabel: "Intro offer", creditsPerDay: 2000, description: "The fastest lane for high-volume, repeatable cleanup.", features: ["Everything in Starter", "Fastest processing lane", "Batch processing", "Priority support", "Batch processing controls"], speed: "Fastest", batch: "Batch processing", retention: "Configurable", support: "Priority support" },
];
export const videosPerDay = (plan: PricingPlan) => plan.creditsPerDay / creditsPerVideo;