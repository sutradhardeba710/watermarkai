"use client";

import { useQuery } from "@tanstack/react-query";

import { paymentsApi } from "@/services/payments";

/** Full-resolution processing cost — mirrors CREDITS_PER_JOB in the backend. */
export const CREDITS_PER_JOB = 100;
/** Quick preview does not deduct credits server-side. */
export const PREVIEW_IS_FREE = true;

/**
 * Live credit balance for the mask workspace. Read-only; used to show honest
 * cost/balance and to gate the insufficient-credits state. Never mutates.
 */
export function useProjectCredits() {
  const query = useQuery({
    queryKey: ["credits"],
    queryFn: () => paymentsApi.credits(),
    staleTime: 30_000,
    retry: 1,
  });

  const balance = query.data?.credits_remaining ?? null;
  const hasEnoughForProcessing =
    balance === null ? true : balance >= CREDITS_PER_JOB;

  return {
    ...query,
    balance,
    planName: query.data?.plan_name ?? null,
    hasEnoughForProcessing,
  };
}
