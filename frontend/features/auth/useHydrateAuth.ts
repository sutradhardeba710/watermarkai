"use client";

import { useEffect } from "react";
import { useAuthStore } from "./authStore";

/** Populates the auth store from localStorage on first client render. */
export function useHydrateAuth() {
  const hydrate = useAuthStore((s) => s.hydrate);
  useEffect(() => {
    hydrate();
  }, [hydrate]);
}
