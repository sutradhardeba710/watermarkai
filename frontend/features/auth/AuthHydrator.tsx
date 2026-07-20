"use client";

import { useEffect } from "react";
import { useAuthStore } from "./authStore";

/**
 * Global auth bootstrap, mounted once in <Providers>.
 *
 * 1. Hydrates the store from localStorage on first client render — every page
 *    (including marketing pages that never called useHydrateAuth) gets the
 *    real session state instead of permanently rendering logged-out.
 * 2. Listens for cross-tab `storage` events so login/logout/token-rotation in
 *    one tab is reflected in all others immediately (prevents a stale tab
 *    from using a revoked refresh token and force-logging the user out).
 */
const AUTH_KEYS = new Set(["vwa_access_token", "vwa_refresh_token", "vwa_user"]);

export function AuthHydrator() {
  const hydrate = useAuthStore((s) => s.hydrate);

  useEffect(() => {
    hydrate();
    const onStorage = (e: StorageEvent) => {
      if (e.key === null || AUTH_KEYS.has(e.key)) hydrate();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [hydrate]);

  return null;
}
