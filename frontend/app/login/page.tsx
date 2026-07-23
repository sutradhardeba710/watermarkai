"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { AuthCard, AuthDivider, AuthError, NamedLink } from "@/components/AuthCard";
import { PasswordField } from "@/components/PasswordField";
import { authApi, type AuthResponse } from "@/services/auth";
import { useAuthStore } from "@/features/auth/authStore";
import { effectiveAdminRole } from "@/features/admin/permissions";
import { GoogleSignInButton } from "@/features/auth/GoogleSignInButton";

function LoginPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const setAuth = useAuthStore((s) => s.setAuth);
  const hydrated = useAuthStore((s) => s.hydrated);
  const currentUser = useAuthStore((s) => s.user);
  const hasSession = useAuthStore((s) => !!s.accessToken);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [googleBusy, setGoogleBusy] = useState(false);

  const deletedAccountMessage = "This account has been deleted and can no longer be accessed. Contact support if you believe this was a mistake.";

  // Surface Google sign-in problems as a toast (transient, non-blocking) while
  // password errors stay inline in the form.
  function handleGoogleError(message: string) {
    setServerError(null);
    toast.error(message);
  }

  // Already logged in? Don't show the login form — go straight to the app
  // (or the requested redirect). session=expired means we were sent here on
  // purpose after a dead session, so the form should show then.
  useEffect(() => {
    if (!hydrated || !hasSession || !currentUser) return;
    if (searchParams.get("session") === "expired") return;
    const redirect = searchParams.get("redirect");
    const safeRedirect = redirect && redirect.startsWith("/") && !redirect.startsWith("//") ? redirect : null;
    const home = effectiveAdminRole(currentUser) ? "/admin" : "/dashboard";
    router.replace(safeRedirect ?? home);
  }, [hydrated, hasSession, currentUser, searchParams, router]);

  // After a user deletes their account, explain the sign-out on return to the
  // login page instead of leaving them with a generic credentials message.
  useEffect(() => {
    if (searchParams.get("deleted") === "1") setServerError(deletedAccountMessage);
  }, [searchParams, deletedAccountMessage]);

  // Honor ?redirect= param (e.g. from /checkout?plan=pro); otherwise admins
  // land on the admin dashboard, everyone else on /dashboard. searchParams
  // .get() already URL-decodes, and only same-origin paths are honored — a
  // full URL here would be an open redirect.
  function goAfterAuth(res: AuthResponse) {
    setAuth(res.access_token, res.refresh_token, res.user);
    const redirect = searchParams.get("redirect");
    const home = effectiveAdminRole(res.user) ? "/admin" : "/dashboard";
    const safeRedirect = redirect && redirect.startsWith("/") && !redirect.startsWith("//") ? redirect : null;
    router.push(safeRedirect ?? home);
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setServerError(null);
    setBusy(true);
    try {
      const res = await authApi.login(email.trim(), password);
      goAfterAuth(res);
    } catch (err: any) {
      if (err?.code === "EMAIL_NOT_VERIFIED") {
        setServerError("Please verify your email before logging in.");
      } else if (err?.code === "ACCOUNT_DELETED") {
        setServerError(deletedAccountMessage);
      } else if (err?.code === "INVALID_CREDENTIALS") {
        setServerError("Invalid email or password.");
      } else if (err?.code === "GOOGLE_ACCOUNT") {
        setServerError('This account signs in with Google. Use "Continue with Google".');
      } else {
        setServerError(err?.message || "Login failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Log in"
      subtitle="Authorized video cleanup studio"
      footer={
        <>
          New here? <NamedLink href="/register">Create an account</NamedLink>
          <span className="mx-2 text-white/30">·</span>
          <NamedLink href="/forgot-password">Forgot password?</NamedLink>
        </>
      }>
      <AuthError msg={serverError} />
      <GoogleSignInButton
        mode="login"
        onSuccess={goAfterAuth}
        onError={handleGoogleError}
        onBusyChange={setGoogleBusy}
      />
      <AuthDivider label="or continue with email" />
      <form
        onSubmit={onSubmit}
        className={`space-y-4 transition-opacity duration-200 ${googleBusy ? "pointer-events-none opacity-40" : ""}`}
        aria-hidden={googleBusy}
        noValidate>

        <div>
          <label htmlFor="login-email" className="mb-1 block text-sm font-medium">Email</label>
          <input
            id="login-email"
            type="email"
            placeholder="you@company.com"
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none transition focus:border-[#4F7CFF] focus:ring-2 focus:ring-[#4F7CFF]/30"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </div>
        <PasswordField
          label="Password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
          placeholder="••••••••"
        />
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-gradient-to-r from-[#4F7CFF] to-[#6D5EF7] px-4 py-2.5 text-white font-medium shadow-[0_8px_24px_-8px_rgba(79,124,255,.6)] transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60">
          {busy ? "Signing in…" : "Log in"}
        </button>
      </form>
    </AuthCard>
  );
}




// useSearchParams() requires a Suspense boundary for static prerender
// (nextjs.org/docs/messages/missing-suspense-with-csr-bailout).
export default function LoginPage() {
  return (
    <Suspense>
      <LoginPageInner />
    </Suspense>
  );
}
