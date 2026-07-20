"use client";

import { useEffect, useState } from "react";

import { mergeLivePlans, pricingPlans, type PricingPlan } from "@/components/pricingPlans";
import { paymentsApi } from "@/services/payments";

export type PlansState = "loading" | "live" | "fallback";

/**
 * Live plan catalog with explicit state, reusing the existing merge logic that
 * is the source of truth (GET /plans, paise→rupees). While loading we return
 * the static defaults so layout doesn't shift; on failure we surface a
 * "fallback" state so the UI can note that standard pricing is shown.
 */
export function useLivePlans(): { plans: PricingPlan[]; state: PlansState } {
  const [plans, setPlans] = useState<PricingPlan[]>(pricingPlans);
  const [state, setState] = useState<PlansState>("loading");

  useEffect(() => {
    let cancelled = false;
    paymentsApi
      .plans()
      .then((live) => {
        if (cancelled) return;
        if (live.length) {
          setPlans(mergeLivePlans(live));
          setState("live");
        } else {
          setState("fallback");
        }
      })
      .catch(() => {
        if (!cancelled) setState("fallback");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { plans, state };
}
