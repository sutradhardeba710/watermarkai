"use client";

import { useEffect } from "react";
import Link from "next/link";
import { RefreshCw } from "lucide-react";

// Route-level error boundary. Without this file, an unexpected render error
// leaves the App Router with no fallback UI and Next.js shows its raw
// "missing required error components, refreshing…" message on a blank page.
export default function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Surface the real cause in the console for debugging.
    console.error("Route error:", error);

    // ChunkLoadError happens when the browser holds a stale page that requests
    // a JS chunk the server rebuilt under a new hash (common after a dev-server
    // recompile or a new deploy). A one-time hard reload pulls the fresh chunks.
    const isChunkError =
      error?.name === "ChunkLoadError" || /Loading chunk .* failed/i.test(error?.message ?? "");
    if (isChunkError && typeof window !== "undefined") {
      const KEY = "cf_chunk_reloaded";
      // Guard against an infinite reload loop if the chunk is genuinely gone.
      if (!sessionStorage.getItem(KEY)) {
        sessionStorage.setItem(KEY, "1");
        window.location.reload();
      }
    } else if (typeof window !== "undefined") {
      // Clear the guard once a normal (non-chunk) render succeeds enough to error.
      sessionStorage.removeItem("cf_chunk_reloaded");
    }
  }, [error]);

  return (
    <main className="grid min-h-dvh place-items-center bg-[#07080f] px-6 text-white">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-white/[.03] p-8 text-center">
        <h1 className="text-lg font-semibold">Something went wrong</h1>
        <p className="mt-2 text-sm leading-6 text-white/55">
          This page hit an unexpected error. You can try again, or head back to your dashboard.
        </p>
        {error?.digest && (
          <p className="mt-3 font-mono text-[11px] text-white/30">Ref: {error.digest}</p>
        )}
        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <button
            onClick={reset}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-110"
          >
            <RefreshCw className="h-4 w-4" />
            Try again
          </button>
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-xl border border-white/10 bg-white/[.03] px-5 py-2.5 text-sm font-semibold text-white/75 transition hover:text-white"
          >
            Go to dashboard
          </Link>
        </div>
      </div>
    </main>
  );
}
