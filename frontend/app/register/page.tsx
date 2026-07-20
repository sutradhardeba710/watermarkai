"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthCard, FieldError, NamedLink } from "@/components/AuthCard";
import { authApi } from "@/services/auth";
import { useAuthStore } from "@/features/auth/authStore";
import { isStrongPassword, STRENGTH_MSG } from "@/utils/password";

export default function RegisterPage() {
  const router = useRouter();
  const hydrated = useAuthStore((s) => s.hydrated);
  const hasSession = useAuthStore((s) => !!s.accessToken && !!s.user);
  // Already logged in — the signup form makes no sense; go to the app.
  useEffect(() => {
    if (hydrated && hasSession) router.replace("/dashboard");
  }, [hydrated, hasSession, router]);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [terms, setTerms] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!fullName.trim()) e.full_name = "Full name is required.";
    if (!email.trim()) e.email = "Email is required.";
    if (!password) e.password = "Password is required.";
    else if (!isStrongPassword(password)) e.password = STRENGTH_MSG;
    if (confirm !== password) e.confirm_password = "Passwords do not match.";
    if (!terms) e.terms = "You must accept the terms to continue.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setServerError(null);
    if (!validate()) return;
    setBusy(true);
    try {
      await authApi.register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        confirm_password: confirm,
        terms_accepted: terms,
      });
      setSubmitted(true);
    } catch (err: any) {
      if (err?.code === "EMAIL_EXISTS") setServerError("An account with this email already exists.");
      else if (err?.code === "WEAK_PASSWORD") setServerError(STRENGTH_MSG);
      else setServerError(err?.message || "Registration failed.");
    } finally {
      setBusy(false);
    }
  }

  if (submitted) {
    return (
      <AuthCard title="Check your email" subtitle="Verification link sent">
        <p className="text-sm text-slate-600">
          We sent a verification link to <span className="font-medium">{email}</span>. Click the
          link to activate your account, then{" "}
          <NamedLink href="/login">log in</NamedLink>.
        </p>
        <p className="mt-3 text-xs text-slate-400">
          (Dev mode: the verification link is also printed in the backend console.)
        </p>
        <div className="mt-6">
          <button
            onClick={() => router.push("/login")}
            className="rounded-md bg-brand-600 px-4 py-2 text-white hover:bg-brand-700">
            Go to login
          </button>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create account"
      subtitle="Authorized video cleanup — for your own or licensed videos."
      footer={
        <>
          Already have an account? <NamedLink href="/login">Log in</NamedLink>
        </>
      }>
      {serverError && (
        <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{serverError}</div>
      )}
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div>
          <label className="mb-1 block text-sm font-medium">Full name</label>
          <input
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none transition focus:border-[#4F7CFF] focus:ring-2 focus:ring-[#4F7CFF]/30"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            autoComplete="name"
          />
          <FieldError msg={errors.full_name} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Email</label>
          <input
            type="email"
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none transition focus:border-[#4F7CFF] focus:ring-2 focus:ring-[#4F7CFF]/30"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
          <FieldError msg={errors.email} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Password</label>
          <input
            type="password"
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none transition focus:border-[#4F7CFF] focus:ring-2 focus:ring-[#4F7CFF]/30"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
          <FieldError msg={errors.password} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Confirm password</label>
          <input
            type="password"
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none transition focus:border-[#4F7CFF] focus:ring-2 focus:ring-[#4F7CFF]/30"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
          />
          <FieldError msg={errors.confirm_password} />
        </div>
        <label className="flex items-start gap-2 text-sm text-white/70">
          <input
            type="checkbox"
            checked={terms}
            onChange={(e) => setTerms(e.target.checked)}
            className="mt-1 h-4 w-4 accent-[#4F7CFF]"
          />
          <span>
            I confirm I have the right to edit my videos and remove their watermarks, logos,
            subtitles, timestamps, or overlays.
          </span>
        </label>
        <FieldError msg={errors.terms} />
        <button
          type="submit"
          disabled={busy || !terms}
          className="w-full rounded-md bg-gradient-to-r from-[#4F7CFF] to-[#6D5EF7] px-4 py-2.5 text-white font-medium transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60">
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>
    </AuthCard>
  );
}




