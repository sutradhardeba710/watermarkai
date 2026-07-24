"use client";

import { Suspense, FormEvent, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { AuthCard, FieldError, NamedLink } from "@/components/AuthCard";
import { authApi } from "@/services/auth";
import { isStrongPassword, STRENGTH_MSG } from "@/utils/password";

function ResetInner() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!password) e.password = "Password is required.";
    else if (!isStrongPassword(password)) e.password = STRENGTH_MSG;
    if (confirm !== password) e.confirm = "Passwords do not match.";
    if (!token) e.token = "Missing reset token.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setServerError(null);
    if (!validate()) return;
    setBusy(true);
    try {
      await authApi.resetPassword(token, password, confirm);
      setDone(true);
      setTimeout(() => router.push("/login"), 1200);
    } catch (err: any) {
      setServerError(err?.message || "Reset failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Reset password"
      subtitle="Choose a new password"
      footer={<NamedLink href="/login">Back to login</NamedLink>}>
      {done ? (
        <p className="text-sm text-emerald-300">Password updated. Redirecting to login…</p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {serverError && (
            <div className="rounded-md bg-rose-500/10 px-3 py-2 text-sm text-rose-200">{serverError}</div>
          )}
          <FieldError msg={errors.token} />
          <div>
            <label htmlFor="reset-password" className="mb-1 block text-sm font-medium">New password</label>
            <input
              id="reset-password"
              type="password"
              className="min-h-12 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 focus:border-[#4f7cff] focus:outline-none"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <FieldError msg={errors.password} />
          </div>
          <div>
            <label htmlFor="reset-confirm" className="mb-1 block text-sm font-medium">Confirm password</label>
            <input
              id="reset-confirm"
              type="password"
              className="min-h-12 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 focus:border-[#4f7cff] focus:outline-none"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            <FieldError msg={errors.confirm} />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="min-h-12 w-full rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-2.5 text-white font-medium hover:brightness-110 disabled:opacity-60">
            {busy ? "Updating…" : "Reset password"}
          </button>
        </form>
      )}
    </AuthCard>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<AuthCard title="Reset password"><p className="text-sm">Loading…</p></AuthCard>}>
      <ResetInner />
    </Suspense>
  );
}

