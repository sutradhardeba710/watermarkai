"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";

import { useAuthStore } from "@/features/auth/authStore";
import { authApi } from "@/services/auth";
import { paymentsApi, type SubscriptionStatus } from "@/services/payments";

/**
 * Shared account-menu state: the authenticated user, their real subscription
 * status (plan, credits, renewal/cancellation), and a guarded logout that
 * reuses the existing auth flow.
 *
 * Uses the same ["billing-status"] query key as the Billing page so the two
 * views share one cache entry instead of double-fetching.
 */
export function useAccountMenu() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const clear = useAuthStore((s) => s.clear);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const ready = useAuthStore((s) => !!s.accessToken);

  const [signingOut, setSigningOut] = useState(false);
  const inFlight = useRef(false);

  const status = useQuery<SubscriptionStatus>({
    queryKey: ["billing-status"],
    queryFn: paymentsApi.status,
    enabled: ready,
  });

  const logout = useCallback(async () => {
    if (inFlight.current) return; // prevent duplicate logout requests
    inFlight.current = true;
    setSigningOut(true);
    try {
      // authApi.logout swallows its own network errors; a throw here is a
      // genuine failure, so keep the session intact and let the user retry.
      await authApi.logout(refreshToken ?? undefined);
      clear();
      router.replace("/login");
    } catch {
      toast.error("Couldn't sign you out. Please try again.");
      inFlight.current = false;
      setSigningOut(false);
    }
  }, [refreshToken, clear, router]);

  return {
    user,
    status: status.data,
    statusLoading: ready && status.isLoading,
    statusError: status.isError,
    signingOut,
    logout,
  };
}
