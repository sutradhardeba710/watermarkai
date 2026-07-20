"use client";
// Global admin search (PRD §29). Debounced query → grouped results across
// users/projects/jobs/payments/subscriptions/promos/workers. Every result
// deep-links to the relevant admin page. The backend classifies the token and
// only probes the tables it could match.
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { adminApi } from "@/services/admin";
import type { GlobalSearch as GlobalSearchResult } from "@/types";

// Map an entity type to the admin route that shows a single record.
const ENTITY_HREF: Record<string, (id: string) => string> = {
  user: (id) => `/admin/users/${id}`,
  project: (id) => `/admin/projects/${id}`,
  job: (id) => `/admin/jobs?q=${id}`,
  payment: (id) => `/admin/payments/${id}`,
  razorpay_payment: (id) => `/admin/payments/${id}`,
  subscription: (id) => `/admin/subscriptions?q=${id}`,
  promo: (id) => `/admin/promos?q=${id}`,
  worker: (id) => `/admin/workers/${id}`,
  abuse_report: (id) => `/admin/abuse?q=${id}`,
};

function labelize(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function GlobalSearch() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<GlobalSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setResults(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const r = await adminApi.search(term);
        if (!cancelled) {
          setResults(r);
          setOpen(true);
        }
      } catch {
        if (!cancelled) setResults(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [q]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  function go(entityType: string, id: string) {
    const build = ENTITY_HREF[entityType];
    if (build) {
      setOpen(false);
      setQ("");
      router.push(build(id));
    }
  }

  const hasResults = results && results.groups.some((g) => g.items.length > 0);

  return (
    <div ref={boxRef} className="relative">
      <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-[#0c0e1a] px-3 py-2">
        <Search className="h-4 w-4 text-white/35" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => results && setOpen(true)}
          placeholder="Search users, payments, jobs…"
          className="w-full bg-transparent text-sm text-white/85 outline-none placeholder:text-white/30"
        />
      </div>
      {open && q.trim().length >= 2 && (
        <div className="absolute z-40 mt-2 max-h-96 w-full overflow-auto rounded-xl border border-white/10 bg-[#10121f] p-2 shadow-xl">
          {loading && <p className="px-2 py-1.5 text-xs text-white/40">Searching…</p>}
          {!loading && !hasResults && (
            <p className="px-2 py-1.5 text-xs text-white/40">No matches.</p>
          )}
          {!loading &&
            results?.groups
              .filter((g) => g.items.length > 0)
              .map((group) => (
                <div key={group.entity_type} className="mb-2 last:mb-0">
                  <p className="px-2 py-1 text-[11px] uppercase tracking-wide text-white/30">
                    {labelize(group.entity_type)}
                  </p>
                  {group.items.map((item) => (
                    <button
                      key={`${group.entity_type}:${item.id}`}
                      onClick={() => go(group.entity_type, item.id)}
                      className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-sm text-white/75 hover:bg-white/5"
                    >
                      <span className="truncate">{item.label}</span>
                      {item.sublabel && (
                        <span className="ml-2 shrink-0 font-mono text-xs text-white/35">{item.sublabel}</span>
                      )}
                    </button>
                  ))}
                </div>
              ))}
        </div>
      )}
    </div>
  );
}
