"use client";

import { useEffect, useState } from "react";

import { useAuthStore } from "@/features/auth/authStore";
import { paymentsApi } from "@/services/payments";

/**
 * Auth-aware marketing state. `useAuthStore` hydrates from localStorage on the
 * client; before hydration we render the logged-out variant to keep SSR output
 * stable (no hydration mismatch). Once hydrated, `isAuthed` reflects the real
 * session and `currentPlanId` is best-effort from the billing status endpoint
 * (the stored auth user carries no plan field). Both loading and failure are
 * tolerated — CTAs simply fall back to their generic labels.
 */
export function useMarketingAuth() {
  const hydrated = useAuthStore((s) => s.hydrated);
  const user = useAuthStore((s) => s.user);
  const [currentPlanId, setCurrentPlanId] = useState<string | null>(null);

  const isAuthed = hydrated && Boolean(user);

  useEffect(() => {
    if (!isAuthed) {
      setCurrentPlanId(null);
      return;
    }
    let cancelled = false;
    paymentsApi
      .status()
      .then((s) => {
        if (!cancelled) setCurrentPlanId(s.plan_id ?? null);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [isAuthed]);

  return {
    hydrated,
    isAuthed,
    userName: user?.full_name || user?.email || null,
    currentPlanId,
  };
}
