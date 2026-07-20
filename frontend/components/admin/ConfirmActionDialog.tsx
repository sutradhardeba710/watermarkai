"use client";
// Confirmation dialog for destructive admin actions (PRD §30.5): states the
// action + target + impact, and collects a required reason when asked.
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

export interface ConfirmActionState {
  title: string;
  description: string;
  confirmLabel: string;
  requireReason?: boolean;
  danger?: boolean;
  /** Optional numeric input (e.g. hours / credit amount). */
  numberLabel?: string;
  numberDefault?: number;
  onConfirm: (reason: string, amount?: number) => Promise<void> | void;
}

export function ConfirmActionDialog({ state, onClose }: {
  state: ConfirmActionState | null;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const [amount, setAmount] = useState<number>(state?.numberDefault ?? 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function confirm() {
    if (!state) return;
    if (state.requireReason && reason.trim().length < 3) {
      setError("Please provide a reason (at least 3 characters).");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await state.onConfirm(reason.trim(), state.numberLabel ? amount : undefined);
      setReason("");
      onClose();
    } catch (err) {
      const message = (err as { message?: string })?.message || "The action could not be completed.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AnimatePresence>
      {state && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, y: 8 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.95, y: 8 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md rounded-2xl border border-white/10 bg-[#10121f] p-6 shadow-2xl"
          >
            <h3 className={`text-lg font-semibold ${state.danger ? "text-rose-200" : "text-white"}`}>{state.title}</h3>
            <p className="mt-2 text-sm leading-6 text-white/60">{state.description}</p>
            {state.numberLabel && (
              <label className="mt-4 block text-sm text-white/75">
                {state.numberLabel}
                <input
                  type="number" min={1} value={amount}
                  onChange={(e) => setAmount(Number(e.target.value))}
                  className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
                />
              </label>
            )}
            {state.requireReason && (
              <label className="mt-4 block text-sm text-white/75">
                Reason <span className="text-rose-300">*</span>
                <textarea
                  value={reason} onChange={(e) => setReason(e.target.value)} rows={2}
                  placeholder="Why is this action being taken?"
                  className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff]"
                />
              </label>
            )}
            {error && <p className="mt-3 text-sm text-rose-300">{error}</p>}
            <div className="mt-6 flex justify-end gap-3">
              <button onClick={onClose} className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white/70 hover:bg-white/5">
                Cancel
              </button>
              <button
                onClick={confirm} disabled={busy}
                className={`rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 ${
                  state.danger ? "bg-rose-500/80 hover:bg-rose-500" : "bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6]"
                }`}
              >
                {busy ? "Working..." : state.confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
