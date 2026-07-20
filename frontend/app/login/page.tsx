"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AuthCard, NamedLink } from "@/components/AuthCard";
import { authApi } from "@/services/auth";
import { useAuthStore } from "@/features/auth/authStore";
import { effectiveAdminRole } from "@/features/admin/permissions";

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

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setServerError(null);
    setBusy(true);
    try {
      const res = await authApi.login(email.trim(), password);
      setAuth(res.access_token, res.refresh_token, res.user);
      // Honor ?redirect= param (e.g. from /checkout?plan=pro); otherwise
      // admins land on the admin dashboard, everyone else on /dashboard.
      // searchParams.get() already URL-decodes, and only same-origin paths
      // are honored — a full URL here would be an open redirect.
      const redirect = searchParams.get("redirect");
      const home = effectiveAdminRole(res.user) ? "/admin" : "/dashboard";
      const safeRedirect = redirect && redirect.startsWith("/") && !redirect.startsWith("//") ? redirect : null;
      router.push(safeRedirect ?? home);
    } catch (err: any) {
      if (err?.code === "EMAIL_NOT_VERIFIED") {
        setServerError("Please verify your email before logging in.");
      } else if (err?.code === "INVALID_CREDENTIALS") {
        setServerError("Invalid email or password.");
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
      {serverError && (
        <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{serverError}</div>
      )}
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div>
          <label className="mb-1 block text-sm font-medium">Email</label>
          <input
            type="email"
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none transition focus:border-[#4F7CFF] focus:ring-2 focus:ring-[#4F7CFF]/30"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Password</label>
          <input
            type="password"
            className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none transition focus:border-[#4F7CFF] focus:ring-2 focus:ring-[#4F7CFF]/30"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-gradient-to-r from-[#4F7CFF] to-[#6D5EF7] px-4 py-2.5 text-white font-medium transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-60">
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
