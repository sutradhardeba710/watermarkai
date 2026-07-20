"use client";
// Secret descriptors (PRD §26.7) — super-admin only. NEVER shows a private
// value: only configured/missing, the last four characters, and (for the public
// razorpay_key_id) the full identifier. The backend guarantees no private value
// reaches the client; this page just renders the descriptor.
import { useQuery } from "@tanstack/react-query";
import { KeyRound, ShieldCheck, ShieldX } from "lucide-react";
import { adminApi } from "@/services/admin";
import { ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AdminSecretsPage() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "secrets"],
    queryFn: () => adminApi.secrets(),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Configuration"
        title="Secrets"
        subtitle="Configured status only — private values are never displayed (§26.7)."
      />
      {error && <ErrorNote text="Unable to load secret descriptors." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((s) => (
            <div key={s.name} className="rounded-xl border border-white/10 bg-[#10121f] p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <KeyRound className="h-4 w-4 text-white/40" />
                  <span className="text-sm font-medium text-white/85">{labelize(s.name)}</span>
                </div>
                {s.configured ? (
                  <span className="flex items-center gap-1 text-xs text-emerald-400">
                    <ShieldCheck className="h-3.5 w-3.5" /> Configured
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-xs text-red-400">
                    <ShieldX className="h-3.5 w-3.5" /> Missing
                  </span>
                )}
              </div>
              <div className="mt-2 font-mono text-xs text-white/50">
                {s.public && s.value ? (
                  <span className="text-white/70">{s.value}</span>
                ) : s.configured ? (
                  <span>••••••••{s.last_four && `  ·  ends ${s.last_four}`}</span>
                ) : (
                  <span className="text-white/30">not set</span>
                )}
              </div>
              {s.updated_at && (
                <p className="mt-1 text-[11px] text-white/30">Updated {s.updated_at}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
