"use client";

import { ArrowRight, Check, Info, LoaderCircle, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CreditEstimate } from "./CreditEstimate";
import { BrittleMaskWarning } from "@/components/BrittleMaskWarning";
import type { SaveState, useMaskWorkspace } from "@/features/mask/useMaskWorkspace";
import type { useProjectCredits } from "@/features/mask/useProjectCredits";
import { cn } from "@/lib/utils";

type Ws = ReturnType<typeof useMaskWorkspace>;
type Credits = ReturnType<typeof useProjectCredits>;

/**
 * Sticky primary-action area. The main button always states the real next
 * system action, and every disabled state carries a reason.
 */
export function WorkspaceActionBar({
  ws,
  credits,
  onSave,
  onDiscard,
  onContinue,
  onPreview,
}: {
  ws: Ws;
  credits: Credits;
  onSave: () => void;
  onDiscard: () => void;
  onContinue: () => void;
  onPreview: () => void;
}) {
  const { hasMask, maskSaved, saveState, saveErr, brittle, readOnly } = ws;
  const saving = saveState === "saving";

  return (
    <section className="rounded-2xl border border-white/10 bg-[#14161d] p-4">
      <CreditEstimate credits={credits} className="mb-3" />

      {brittle && (
        <div className="mb-3">
          <BrittleMaskWarning brittle={brittle} />
        </div>
      )}

      {saveErr && (
        <p role="alert" className="mb-3 rounded-xl border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-xs leading-5 text-rose-200">
          {saveErr}
        </p>
      )}

      {readOnly ? (
        <div className="rounded-xl border border-white/[.08] bg-black/20 px-3 py-3 text-center text-xs leading-5 text-white/50">
          This project is read-only. You can review the saved mask but can&apos;t make changes.
        </div>
      ) : !hasMask ? (
        <>
          <Button variant="primary" className="w-full" disabled title="Create or accept a mask first">
            Create a mask to continue
          </Button>
          <p className="mt-2 flex items-center justify-center gap-1.5 text-[11px] text-white/40">
            <Info className="h-3 w-3" /> Draw a selection or run AI Detect to enable this.
          </p>
        </>
      ) : !maskSaved ? (
        <>
          <Button variant="primary" className="w-full" onClick={onSave} disabled={saving}>
            {saving ? <><LoaderCircle className="h-4 w-4 animate-spin motion-reduce:animate-none" /> Saving…</> : "Save mask"}
          </Button>
          <Button variant="ghost" size="sm" className="mt-2 w-full" onClick={onDiscard} disabled={saving}>
            Discard changes
          </Button>
          <p className="mt-2 text-center text-[11px] text-white/40">Save to unlock preview and processing.</p>
        </>
      ) : (
        <>
          <Button variant="primary" className="w-full" onClick={onContinue}>
            Continue <ArrowRight className="h-4 w-4" />
          </Button>
          <Button variant="accent" size="sm" className="mt-2 w-full" onClick={onPreview}>
            <Sparkles className="h-4 w-4" /> Generate quick preview
            <span className="ml-auto rounded-full bg-emerald-400/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">Free</span>
          </Button>
          <p className="mt-2 flex items-center justify-center gap-1.5 text-center text-[11px] text-emerald-300/80">
            <Check className="h-3 w-3" /> Static selection — tracking is not required.
          </p>
        </>
      )}
    </section>
  );
}
