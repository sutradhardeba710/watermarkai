"use client";

import { useQuery } from "@tanstack/react-query";

import { useAuthStore } from "@/features/auth/authStore";
import type { SubscriptionStatus } from "@/services/payments";

/**
 * Auth-aware marketing state. `useAuthStore` hydrates from localStorage on the
 * client; before hydration we render the logged-out variant to keep SSR output
 * stable. Public marketing pages never probe a protected endpoint just to
 * personalize CTA labels, so `currentPlanId` only observes billing data already
 * cached by an authenticated account or billing screen.
 */
export function useMarketingAuth() {
  const hydrated = useAuthStore((s) => s.hydrated);
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const { data: cachedStatus } = useQuery<SubscriptionStatus>({
    queryKey: ["billing-status"],
    queryFn: async () => {
      throw new Error("Marketing billing status is cache-only.");
    },
    enabled: false,
    retry: false,
  });

  const isAuthed = hydrated && Boolean(accessToken && user);

  return {
    hydrated,
    isAuthed,
    userName: user?.full_name || user?.email || null,
    currentPlanId: isAuthed ? cachedStatus?.plan_id ?? null : null,
  };
}