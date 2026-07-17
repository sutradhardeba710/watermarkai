"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthCard, NamedLink } from "@/components/AuthCard";
import { authApi } from "@/services/auth";
import { useAuthStore } from "@/features/auth/authStore";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setServerError(null);
    setBusy(true);
    try {
      const res = await authApi.login(email.trim(), password);
      setAuth(res.access_token, res.refresh_token, res.user);
      router.push("/dashboard");
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



