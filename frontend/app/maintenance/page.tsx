"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Clock3, Wrench } from "lucide-react";

type MaintenanceStatus = {
  maintenance_enabled: boolean;
  public_message: string;
  end_time: string | null;
  status_page_link: string | null;
};

/** Public maintenance page. Polls the unauthenticated status endpoint and
 * sends visitors back home automatically once maintenance ends. */
export default function MaintenancePage() {
  const [status, setStatus] = useState<MaintenanceStatus | null>(null);

  useEffect(() => {
    let timer: number | undefined;
    const check = async () => {
      try {
        const res = await fetch("/health/maintenance", { cache: "no-store" });
        if (res.ok) {
          const data: MaintenanceStatus = await res.json();
          setStatus(data);
          if (!data.maintenance_enabled) {
            window.location.assign("/");
            return;
          }
        }
      } catch {
        // Backend unreachable — keep showing the page and retry.
      }
      timer = window.setTimeout(check, 15000);
    };
    void check();
    return () => window.clearTimeout(timer);
  }, []);

  const message =
    status?.public_message ||
    "We're performing scheduled maintenance. Please check back soon.";

  return (
    <main className="grid min-h-screen place-items-center bg-[#07080f] px-5 text-[#f5f6fa]">
      <div className="w-full max-w-lg text-center">
        <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl border border-[#4f7cff]/20 bg-gradient-to-br from-[#4f7cff]/20 to-[#6d5ef7]/10 text-[#9eb4ff]">
          <Wrench className="h-7 w-7" />
        </div>
        <h1 className="mt-6 text-3xl font-semibold tracking-tight">
          We&apos;ll be right back
        </h1>
        <p className="mt-4 leading-7 text-white/60">{message}</p>
        {status?.end_time && (
          <p className="mt-4 flex items-center justify-center gap-2 text-sm text-white/45">
            <Clock3 className="h-4 w-4" />
            Expected back by {new Date(status.end_time).toLocaleString()}
          </p>
        )}
        {status?.status_page_link && (
          <Link
            href={status.status_page_link}
            className="mt-6 inline-flex min-h-11 items-center justify-center rounded-xl border border-white/10 px-5 py-2.5 text-sm text-white/70 transition hover:bg-white/5 hover:text-white"
          >
            View status page
          </Link>
        )}
        <p className="mt-8 text-xs text-white/30">
          This page refreshes automatically every 15 seconds.
        </p>
      </div>
    </main>
  );
}
