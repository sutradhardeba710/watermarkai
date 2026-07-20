"use client";

import Link from "next/link";
import { CloudOff, Clock, RefreshCw, TriangleAlert, WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";

type Kind = "offline" | "expired" | "load-error";

const CONFIG: Record<Kind, { icon: React.ElementType; tone: string }> = {
  offline: { icon: WifiOff, tone: "amber" },
  expired: { icon: Clock, tone: "rose" },
  "load-error": { icon: TriangleAlert, tone: "rose" },
};

/**
 * Full-page error/warning state. Every message states what happened, that work
 * is safe where true, a recommended action, retry, and a support ref for
 * technical failures — no raw backend exceptions.
 */
export function WorkspaceErrorState({
  kind,
  message,
  referenceId,
  onRetry,
}: {
  kind: Kind;
  message?: string;
  referenceId?: string;
  onRetry?: () => void;
}) {
  const { icon: Icon, tone } = CONFIG[kind];
  const toneClass = tone === "amber" ? "border-amber-400/20 bg-amber-400/10 text-amber-300" : "border-rose-400/20 bg-rose-500/10 text-rose-300";

  const copy = {
    offline: {
      title: "You're offline",
      body: "We lost the network connection. Your mask work is safe and will still be here when you reconnect.",
    },
    expired: {
      title: "This project has expired",
      body: "The source video for this project is no longer available. Start a new project to clean another video.",
    },
    "load-error": {
      title: "We couldn't load this project",
      body: message || "Something went wrong while loading the workspace. Please try again.",
    },
  }[kind];

  return (
    <main className="grid min-h-dvh place-items-center bg-[#07080f] px-6 text-white">
      <div className="w-full max-w-md rounded-3xl border border-white/10 bg-[#10121f] p-8 text-center">
        <div className={`mx-auto grid h-14 w-14 place-items-center rounded-2xl border ${toneClass}`}>
          <Icon className="h-6 w-6" />
        </div>
        <h1 className="mt-5 text-lg font-semibold">{copy.title}</h1>
        <p className="mt-2 text-sm leading-6 text-white/55">{copy.body}</p>

        <div className="mt-6 flex flex-col gap-2.5">
          {onRetry && (
            <Button variant="primary" onClick={onRetry}>
              <RefreshCw className="h-4 w-4" /> Try again
            </Button>
          )}
          <Button variant="secondary" asChild>
            <Link href="/dashboard">Back to dashboard</Link>
          </Button>
        </div>

        {referenceId && (
          <p className="mt-4 inline-flex items-center gap-1.5 text-[11px] text-white/30">
            <CloudOff className="h-3 w-3" /> Support reference: {referenceId}
          </p>
        )}
      </div>
    </main>
  );
}

/** Small inline banner used when connectivity drops mid-session. */
export function OfflineBanner({ reconnecting }: { reconnecting: boolean }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-center gap-2 bg-amber-500/15 px-4 py-1.5 text-xs font-medium text-amber-100"
    >
      <WifiOff className="h-3.5 w-3.5" />
      {reconnecting ? "Reconnecting…" : "You're offline. Your work is saved locally and safe."}
    </div>
  );
}
