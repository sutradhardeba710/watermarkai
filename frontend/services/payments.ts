import { api } from "./api";

export interface SubscribeResponse {
  razorpay_subscription_id: string;
  razorpay_key_id: string;
  plan_name: string;
  amount_inr: number;
}

export interface PromoValidateResponse {
  valid: boolean;
  discount_percent: number | null;
  message: string | null;
  original_amount: number | null;  // rupees, server-authoritative
  discount_amount: number | null;
  final_amount: number | null;
}

export interface SubscriptionStatus {
  plan_id: string;
  plan_name: string;
  credits_per_day: number;
  credits_remaining: number;
  subscription_status: string | null;
  razorpay_subscription_id: string | null;
  current_period_end: string | null;
  is_free: boolean;
}

export interface CreditStatus {
  plan_id: string;
  plan_name: string;
  credits_per_day: number;
  credits_remaining: number;
  credits_used_today: number;
}

export interface PublicPlan {
  id: string;
  name: string;
  description: string | null;
  price_inr: number; // paise
  annual_price_inr: number | null;
  currency: string;
  billing_interval: string;
  credits_per_day: number;
  monthly_credits: number | null;
  is_recommended: boolean;
  display_order: number;
  max_upload_mb: number | null;
  max_duration_seconds: number | null;
  max_resolution: string | null;
  concurrent_jobs: number | null;
  storage_allowance_mb: number | null;
  retention_days: number | null;
  priority_level: number | null;
  api_access: boolean | null;
  support_level: string | null;
}

export const paymentsApi = {
  /** Public plan catalog (no auth) — live DB data so admin edits show immediately. */
  plans: async (): Promise<PublicPlan[]> => {
    const res = await api.get<PublicPlan[]>("/plans");
    return res.data;
  },

  /** Create a Razorpay subscription and return details for the checkout modal. */
  subscribe: async (planId: string, promoCode?: string): Promise<SubscribeResponse> => {
    const res = await api.post<SubscribeResponse>("/payments/subscribe", { 
      plan_id: planId,
      promo_code: promoCode || null
    });
    return res.data;
  },

  /** Validate a promo code against a plan; returns server-computed pricing. */
  validatePromo: async (code: string, planId?: string): Promise<PromoValidateResponse> => {
    const res = await api.post<PromoValidateResponse>("/payments/promo/validate", {
      code,
      plan_id: planId ?? null,
    });
    return res.data;
  },

  /** Get current user's subscription status and credit balance. */
  status: async (): Promise<SubscriptionStatus> => {
    const res = await api.get<SubscriptionStatus>("/payments/status");
    return res.data;
  },

  /** Cancel current subscription. */
  cancel: async (reason?: string): Promise<{ success: boolean; message: string }> => {
    const res = await api.post<{ success: boolean; message: string }>("/payments/cancel", {
      reason: reason ?? null,
    });
    return res.data;
  },

  /** Lightweight credit balance for dashboard widget. */
  credits: async (): Promise<CreditStatus> => {
    const res = await api.get<CreditStatus>("/credits");
    return res.data;
  },
};
