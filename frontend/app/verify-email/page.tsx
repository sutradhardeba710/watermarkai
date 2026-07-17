"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AuthCard, NamedLink } from "@/components/AuthCard";
import { authApi } from "@/services/auth";

function VerifyInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("No verification token provided.");
      return;
    }
    authApi
      .verifyEmail(token)
      .then(() => {
        setStatus("ok");
        setMessage("Your email is verified. You can now log in.");
      })
      .catch((e) => {
        setStatus("error");
        setMessage(e?.message || "Verification failed.");
      });
  }, [token]);

  return (
    <AuthCard title="Verifying email" subtitle="Confirming your account…">
      {status === "loading" && <p className="text-sm text-white/65">Please wait…</p>}
      {status === "ok" && (
        <div>
          <p className="text-sm text-emerald-300">{message}</p>
          <div className="mt-6">
            <NamedLink href="/login">Go to login</NamedLink>
          </div>
        </div>
      )}
      {status === "error" && (
        <div>
          <p className="text-sm text-rose-200">{message}</p>
          <div className="mt-6">
            <NamedLink href="/register">Back to register</NamedLink>
          </div>
        </div>
      )}
    </AuthCard>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<AuthCard title="Verifying email"><p className="text-sm">Loading…</p></AuthCard>}>
      <VerifyInner />
    </Suspense>
  );
}

