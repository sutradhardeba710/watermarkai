"use client";

import { FormEvent, useState } from "react";
import { AuthCard, NamedLink } from "@/components/AuthCard";
import { authApi } from "@/services/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await authApi.forgotPassword(email.trim());
      setDone(true);
    } catch (e: any) {
      setError(e?.message || "Request failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Forgot password"
      subtitle="We'll send a reset link to your email"
      footer={<NamedLink href="/login">Back to login</NamedLink>}>
      {done ? (
        <p className="text-sm text-white/65">
          If that email exists, a reset link has been sent. Check your inbox (or the backend
          console in dev mode).
        </p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          {error && (
            <div className="rounded-md bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{error}</div>
          )}
          <div>
            <label className="mb-1 block text-sm font-medium">Email</label>
            <input
              type="email"
              className="min-h-12 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 focus:border-[#4f7cff] focus:outline-none"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="min-h-12 w-full rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-2.5 text-white font-medium hover:brightness-110 disabled:opacity-60">
            {busy ? "Sending…" : "Send reset link"}
          </button>
        </form>
      )}
    </AuthCard>
  );
}

