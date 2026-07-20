"use client";

import Link from "next/link";
import { Coins, TriangleAlert } from "lucide-react";

import { CREDITS_PER_JOB, type useProjectCredits } from "@/features/mask/useProjectCredits";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Credits = ReturnType<typeof useProjectCredits>;

/**
 * Honest cost + balance. Quick preview is free (backend deducts nothing); full
 * processing costs CREDITS_PER_JOB. Upgrade prompt appears ONLY when the balance
 * is short — no aggressive upsell inside the editor.
 */
export function CreditEstimate({ credits, className }: { credits: Credits; className?: string }) {
  const { balance, isLoading, hasEnoughForProcessing } = credits;
  const short = !isLoading && !hasEnoughForProcessing;

  return (
    <div className={cn("rounded-xl border border-white/[.08] bg-black/20 p-3 text-xs", className)}>
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-white/50">
          <Coins className="h-3.5 w-3.5" /> Cost
        </span>
        {isLoading ? (
          <span className="text-white/30">Checking balance…</span>
        ) : balance != null ? (
          <span className={cn("font-medium", short ? "text-rose-300" : "text-white/70")}>
            Balance: {balance} credit{balance === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>
      <div className="mt-2 space-y-1">
        <Row label="Quick preview" value="Free" tone="free" />
        <Row label="Full processing" value={`${CREDITS_PER_JOB} credits`} />
      </div>

      {short && (
        <div className="mt-2.5 rounded-lg border border-rose-400/20 bg-rose-500/10 p-2.5">
          <p className="flex items-start gap-1.5 text-rose-200">
            <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>You need {CREDITS_PER_JOB} credits to process the full video. You can still build a free preview.</span>
          </p>
          <Button variant="secondary" size="sm" className="mt-2 w-full" asChild>
            <Link href="/pricing">Compare plans</Link>
          </Button>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "free" }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-white/45">{label}</span>
      <span className={cn("font-medium", tone === "free" ? "text-emerald-300" : "text-white/75")}>{value}</span>
    </div>
  );
}
