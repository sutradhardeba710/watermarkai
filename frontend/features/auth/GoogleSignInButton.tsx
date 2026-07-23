"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { authApi } from "@/services/auth";
import type { AuthResponse } from "@/services/auth";

const GIS_SCRIPT_SRC = "https://accounts.google.com/gsi/client";
const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";
const GIS_LOAD_TIMEOUT_MS = 10_000;

type Phase = "idle" | "authenticating";
type GisCredentialResponse = { credential?: string };
type CredentialHandler = (credential: string) => void;

type GoogleIdentityApi = {
  initialize: (config: {
    client_id: string;
    callback: (response: GisCredentialResponse) => void;
  }) => void;
  renderButton: (
    parent: HTMLElement,
    options: {
      type: "standard";
      theme: "filled_black";
      size: "large";
      text: "signup_with" | "continue_with";
      shape: "rectangular";
      logo_alignment: "left";
      width: number;
    },
  ) => void;
};

type GisRuntimeState = {
  initializedClientId: string | null;
  activeCredentialHandler: CredentialHandler | null;
};

type GisWindow = Window & {
  google?: { accounts?: { id?: GoogleIdentityApi } };
  __clearFrameGisState?: GisRuntimeState;
};

let gisScriptPromise: Promise<void> | null = null;

function getGisRuntimeState(): GisRuntimeState {
  const browser = window as GisWindow;
  browser.__clearFrameGisState ??= {
    initializedClientId: null,
    activeCredentialHandler: null,
  };
  return browser.__clearFrameGisState;
}

/** Load Google Identity Services once and allow a clean retry after failure. */
function loadGisScript(): Promise<void> {
  const browser = window as GisWindow;
  if (browser.google?.accounts?.id) return Promise.resolve();
  if (gisScriptPromise) return gisScriptPromise;

  gisScriptPromise = new Promise<void>((resolve, reject) => {
    let timeoutId: number | null = null;

    const finish = () => {
      if (timeoutId !== null) window.clearTimeout(timeoutId);
      if (browser.google?.accounts?.id) {
        resolve();
      } else {
        reject(new Error("Google Identity Services loaded without an identity API."));
      }
    };
    const fail = () => {
      if (timeoutId !== null) window.clearTimeout(timeoutId);
      reject(new Error("Failed to load Google Identity Services."));
    };

    timeoutId = window.setTimeout(fail, GIS_LOAD_TIMEOUT_MS);
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${GIS_SCRIPT_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", finish, { once: true });
      existing.addEventListener("error", fail, { once: true });
      return;
    }

    const script = document.createElement("script");
    script.src = GIS_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", finish, { once: true });
    script.addEventListener("error", fail, { once: true });
    document.head.appendChild(script);
  }).catch((error) => {
    gisScriptPromise = null;
    throw error;
  });

  return gisScriptPromise;
}

/**
 * GIS owns one implicit client per page. Keep its state on window so React
 * Strict Mode and Fast Refresh cannot initialize it more than once.
 */
function initializeGoogleIdentity(clientId: string): GoogleIdentityApi {
  const browser = window as GisWindow;
  const identity = browser.google?.accounts?.id;
  if (!identity) throw new Error("Google Identity Services is unavailable.");

  const runtime = getGisRuntimeState();
  if (runtime.initializedClientId && runtime.initializedClientId !== clientId) {
    throw new Error("Google sign-in configuration changed. Reload this page and try again.");
  }

  if (!runtime.initializedClientId) {
    identity.initialize({
      client_id: clientId,
      callback: (response) => {
        if (response.credential) runtime.activeCredentialHandler?.(response.credential);
      },
    });
    runtime.initializedClientId = clientId;
  }

  return identity;
}

function GoogleMark({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="#4285F4" d="M23.52 12.27c0-.82-.07-1.6-.2-2.36H12v4.46h6.47a5.53 5.53 0 0 1-2.4 3.63v3.02h3.88c2.27-2.09 3.57-5.17 3.57-8.75Z" />
      <path fill="#34A853" d="M12 24c3.24 0 5.96-1.08 7.95-2.91l-3.88-3.02c-1.08.72-2.45 1.15-4.07 1.15-3.13 0-5.78-2.11-6.73-4.96H1.29v3.12A12 12 0 0 0 12 24Z" />
      <path fill="#FBBC05" d="M5.27 14.26a7.2 7.2 0 0 1 0-4.52V6.62H1.29a12 12 0 0 0 0 10.76l3.98-3.12Z" />
      <path fill="#EA4335" d="M12 4.77c1.76 0 3.35.61 4.6 1.8l3.44-3.44A11.98 11.98 0 0 0 12 0 12 12 0 0 0 1.29 6.62l3.98 3.12C6.22 6.88 8.87 4.77 12 4.77Z" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg className="h-5 w-5 animate-spin text-white/90" viewBox="0 0 24 24" aria-hidden="true">
      <circle className="opacity-20" cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="3" />
      <path className="opacity-90" fill="currentColor" d="M12 3a9 9 0 0 1 9 9h-3a6 6 0 0 0-6-6V3Z" />
    </svg>
  );
}

export function GoogleSignInButton({
  onSuccess,
  onError,
  mode = "login",
  onBusyChange,
}: {
  onSuccess: (res: AuthResponse) => void;
  onError: (message: string) => void;
  mode?: "login" | "register";
  onBusyChange?: (busy: boolean) => void;
}) {
  const successLabel = mode === "register" ? "Creating your account…" : "Signing you in…";
  const containerRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const phaseRef = useRef<Phase>("idle");
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  const onBusyChangeRef = useRef(onBusyChange);

  onSuccessRef.current = onSuccess;
  onErrorRef.current = onError;
  onBusyChangeRef.current = onBusyChange;

  const setPhaseSafe = useCallback((next: Phase) => {
    phaseRef.current = next;
    setPhase(next);
    onBusyChangeRef.current?.(next !== "idle");
  }, []);

  const handleCredential = useCallback(
    async (credential: string) => {
      if (phaseRef.current === "authenticating") return;
      setPhaseSafe("authenticating");
      try {
        const response = await authApi.googleLogin(credential);
        onSuccessRef.current(response);
      } catch (error: any) {
        setPhaseSafe("idle");
        if (error?.code === "EMAIL_NOT_VERIFIED" || error?.code === "ACCOUNT_UNVERIFIED") {
          onErrorRef.current(
            "This email is already registered but not verified. Log in with your password and verify it before using Google sign-in.",
          );
        } else if (error?.code === "GOOGLE_ACCOUNT_CONFLICT" || error?.code === "ACCOUNT_EXISTS") {
          onErrorRef.current("An account with this email already exists. Please log in with your password.");
        } else if (error?.response?.status >= 500 || error?.code === "ECONNABORTED" || !error?.response) {
          onErrorRef.current("Google sign-in is temporarily unavailable. Please try again in a moment.");
        } else {
          onErrorRef.current(error?.message || "We couldn’t complete Google sign-in. Please try again.");
        }
      }
    },
    [setPhaseSafe],
  );

  useEffect(() => {
    if (!CLIENT_ID) return;

    let cancelled = false;
    const runtime = getGisRuntimeState();
    runtime.activeCredentialHandler = handleCredential;
    setReady(false);

    loadGisScript()
      .then(() => {
        if (cancelled || !containerRef.current) return;

        const identity = initializeGoogleIdentity(CLIENT_ID);
        const container = containerRef.current;
        container.replaceChildren();
        const width = Math.min(400, Math.max(200, Math.floor(container.getBoundingClientRect().width || 320)));
        identity.renderButton(container, {
          type: "standard",
          theme: "filled_black",
          size: "large",
          text: mode === "register" ? "signup_with" : "continue_with",
          shape: "rectangular",
          logo_alignment: "left",
          width,
        });
        setReady(true);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setReady(false);
        setPhaseSafe("idle");
        onErrorRef.current(
          error instanceof Error ? error.message : "Could not load Google sign-in. Check your connection and try again.",
        );
      });

    return () => {
      cancelled = true;
      if (runtime.activeCredentialHandler === handleCredential) {
        runtime.activeCredentialHandler = null;
      }
      containerRef.current?.replaceChildren();
    };
  }, [handleCredential, mode, setPhaseSafe]);

  if (!CLIENT_ID) {
    return (
      <div className="w-full">
        <button
          type="button"
          disabled
          aria-disabled="true"
          className="flex h-12 w-full cursor-not-allowed items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[.03] text-sm font-medium text-white/40">
          <GoogleMark className="h-5 w-5 opacity-40" />
          Google sign-in unavailable
        </button>
        <p className="mt-2 text-center text-xs text-white/35">
          Google sign-in isn&apos;t configured yet. Please use email and password below.
        </p>
      </div>
    );
  }

  const busy = phase === "authenticating";

  return (
    <div className="w-full">
      <div className="relative min-h-12 w-full">
        <div
          className={`grid min-h-12 w-full place-items-center transition-opacity duration-150 ${busy ? "opacity-0" : "opacity-100"}`}
          aria-hidden={busy}>
          <div ref={containerRef} className="w-full overflow-hidden rounded-xl" />
        </div>

        {!ready && !busy && (
          <div className="pointer-events-none absolute inset-0 animate-pulse rounded-xl border border-white/10 bg-white/[.04]" />
        )}

        {busy && (
          <div
            className="absolute inset-0 flex h-12 items-center justify-center gap-3 rounded-xl border border-white/12 bg-white/[.04] text-sm font-medium text-white"
            role="status"
            aria-live="polite">
            <Spinner />
            {successLabel}
          </div>
        )}
      </div>

      <p className="mt-2.5 flex items-center justify-center gap-1.5 text-center text-xs leading-5 text-white/40">
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
          <rect x="5" y="11" width="14" height="9" rx="2" />
          <path d="M8 11V8a4 4 0 0 1 8 0v3" strokeLinecap="round" />
        </svg>
        Secure Google sign-in. Account selection happens in a Google-managed window.
      </p>
    </div>
  );
}
