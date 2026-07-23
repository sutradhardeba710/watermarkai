"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { AuthCard, AuthDivider, AuthError, FieldError, NamedLink } from "@/components/AuthCard";
import { PasswordField } from "@/components/PasswordField";
import { authApi, type AuthResponse } from "@/services/auth";
import { useAuthStore } from "@/features/auth/authStore";
import { GoogleSignInButton } from "@/features/auth/GoogleSignInButton";
import { isStrongPassword, STRENGTH_MSG } from "@/utils/password";

export default function RegisterPage() {
  const router = useRouter();
  const hydrated = useAuthStore((s) => s.hydrated);
  const hasSession = useAuthStore((s) => !!s.accessToken && !!s.user);
  const setAuth = useAuthStore((s) => s.setAuth);
  // Already logged in — the signup form makes no sense; go to the app.
  useEffect(() => {
    if (hydrated && hasSession) router.replace("/dashboard");
  }, [hydrated, hasSession, router]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [terms, setTerms] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!email.trim()) e.email = "Email is required.";
    if (!password) e.password = "Password is required.";
    else if (!isStrongPassword(password)) e.password = STRENGTH_MSG;
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
      const emailTrimmed = email.trim();
      await authApi.register({
        full_name: emailTrimmed.split("@")[0] || emailTrimmed,
        email: emailTrimmed,
        password,
        confirm_password: password,
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

  // Google sign-in creates a verified account and hands back a session
  // immediately, so it skips the email-verification step and goes straight to
  // the dashboard — unlike the password signup flow above.
  function goAfterAuth(res: AuthResponse) {
    setAuth(res.access_token, res.refresh_token, res.user);
    router.push("/dashboard");
  }

  // Google errors go to a toast; the inline banner is reserved for password
  // form validation and the register API.
  function handleGoogleError(message: string) {
    setServerError(null);
    toast.error(message);
  }

  if (submitted) {
    return (
      <AuthCard title="Check your email" subtitle="Verification link sent">
        <div className="mb-5 grid h-12 w-12 place-items-center rounded-full bg-[#4F7CFF]/15 text-[#9eb4ff]">
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.7">
            <rect x="3" y="5" width="18" height="14" rx="2" />
            <path d="m3 7 9 6 9-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <p className="text-sm leading-6 text-white/70">
          We sent a verification link to <span className="font-medium text-white">{email}</span>. Click
          the link to activate your account, then{" "}
          <NamedLink href="/login">log in</NamedLink>.
        </p>
        <p className="mt-3 text-xs text-white/40">
          (Dev mode: the verification link is also printed in the backend console.)
        </p>
        <div className="mt-6">
          <button
            onClick={() => router.push("/login")}
            className="w-full rounded-xl bg-gradient-to-r from-[#4F7CFF] to-[#6D5EF7] px-4 py-2.5 text-white font-medium shadow-[0_8px_24px_-8px_rgba(79,124,255,.6)] transition hover:opacity-95">
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
      <AuthError msg={serverError} />
      <GoogleSignInButton
        mode="register"
        onSuccess={goAfterAuth}
        onError={handleGoogleError}
        onBusyChange={setGoogleBusy}
      />
      <AuthDivider label="or sign up with email" />
      <form
        onSubmit={onSubmit}
        className={`space-y-4 transition-opacity duration-200 ${googleBusy ? "pointer-events-none opacity-40" : ""}`}
        aria-hidden={googleBusy}
        noValidate>

        <div>
          <label htmlFor="register-email" className="mb-1 block text-sm font-medium">Email</label>
          <input
            id="register-email"
            type="email"
            placeholder="you@company.com"
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none transition focus:border-[#4F7CFF] focus:ring-2 focus:ring-[#4F7CFF]/30"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
          <FieldError msg={errors.email} />
        </div>
        <div>
          <PasswordField
            label="Password"
            value={password}
            onChange={setPassword}
            autoComplete="new-password"
            placeholder="Create a strong password"
            showStrength
          />
          <FieldError msg={errors.password} />
        </div>
        <label className="flex items-start gap-2.5 text-sm text-white/70">
          <input
            type="checkbox"
            checked={terms}
            onChange={(e) => setTerms(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-[#4F7CFF]"
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
          className="w-full rounded-xl bg-gradient-to-r from-[#4F7CFF] to-[#6D5EF7] px-4 py-2.5 text-white font-medium shadow-[0_8px_24px_-8px_rgba(79,124,255,.6)] transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60">
          {busy ? "Creating account…" : "Create account"}
        </button>
      </form>
    </AuthCard>
  );
}




