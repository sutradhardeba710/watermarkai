"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { Bell, CreditCard, FolderKanban, LogOut, Sparkles, Upload, Zap } from "lucide-react";

import { useAuthStore } from "@/features/auth/authStore";
import { authApi } from "@/services/auth";
import { paymentsApi, type CreditStatus } from "@/services/payments";
import { UserMenu } from "@/features/account/UserMenu";

/** ClearFrame wordmark — links home. Identical across every workspace page. */
function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5 text-lg font-semibold tracking-tight text-white">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] text-white shadow-[0_0_22px_rgba(79,124,255,.35)]">
        <Sparkles className="h-5 w-5" />
      </span>
      ClearFrame
    </Link>
  );
}

const NAV = [
  { href: "/dashboard", label: "Projects", icon: FolderKanban },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/billing", label: "Billing", icon: CreditCard },
];

function NavLink({ href, label, icon: Icon, active }: { href: string; label: string; icon: typeof FolderKanban; active: boolean }) {
  if (active) {
    return (
      <Link
        href={href}
        aria-current="page"
        className="relative flex min-h-11 items-center gap-3 rounded-xl border border-[#4f7cff]/25 bg-gradient-to-r from-[#4f7cff]/15 to-[#8b5cf6]/10 px-3 py-2.5 font-medium text-white"
      >
        <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-gradient-to-b from-[#4f7cff] to-[#8b5cf6]" />
        <Icon className="h-4 w-4 text-[#9db9ff]" />
        {label}
      </Link>
    );
  }
  return (
    <Link
      href={href}
      className="flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-white/55 transition hover:bg-white/5 hover:text-white"
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}

/** Daily-credit meter shown at the foot of the sidebar; links to Billing. */
function CreditWidget({ credits }: { credits: CreditStatus | undefined }) {
  if (!credits) return null;
  const pct = credits.credits_per_day > 0 ? Math.min(100, (credits.credits_remaining / credits.credits_per_day) * 100) : 0;
  const barColor = pct < 20 ? "from-rose-500 to-rose-400" : pct < 50 ? "from-amber-400 to-amber-300" : "from-[#4f7cff] to-[#6d5ef7]";
  return (
    <Link href="/billing" className="block rounded-2xl border border-white/10 bg-white/[.03] p-4 transition hover:border-white/20">
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-1.5 font-medium text-cyan-200"><Zap className="h-3 w-3" />{credits.plan_name}</span>
        <span className="text-white/55">{credits.credits_remaining.toLocaleString("en-IN")} cr</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className={`h-full rounded-full bg-gradient-to-r ${barColor} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1.5 text-[10px] text-white/35">{credits.credits_remaining} / {credits.credits_per_day} credits today</p>
      {credits.plan_id === "free" && <p className="mt-2 text-[10px] font-medium text-[#b7c7ff] hover:text-white">Upgrade for more →</p>}
    </Link>
  );
}

type WorkspaceShellProps = {
  children: React.ReactNode;
  title: string;
  eyebrow?: string;
  /** Header controls rendered left of the bell (search, primary action, etc.). */
  actions?: React.ReactNode;
};

/**
 * The single workspace frame (sidebar + header) shared by Projects, Upload, and
 * Billing so the shell no longer changes shape as the user navigates between
 * them. Active nav state is derived from the current pathname; credits + logout
 * are handled internally so pages just supply their title and content.
 */
export function WorkspaceShell({ children, title, eyebrow = "Workspace", actions }: WorkspaceShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const clear = useAuthStore((s) => s.clear);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const ready = useAuthStore((s) => !!s.accessToken);

  const { data: credits } = useQuery<CreditStatus>({
    queryKey: ["credits"],
    queryFn: paymentsApi.credits,
    enabled: ready,
  });

  async function logout() {
    await authApi.logout(refreshToken ?? undefined);
    clear();
    router.replace("/login");
  }

  return (
    <main className="min-h-dvh bg-[#07080f] text-[#f5f6fa] lg:pl-64">
      <div className="pointer-events-none fixed left-1/2 top-0 z-0 h-96 w-[60rem] -translate-x-1/2 bg-[radial-gradient(ellipse_at_top,rgba(79,124,255,.08),transparent_65%)]" />

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-white/[.07] bg-[#0a0c18] px-4 py-6 lg:flex">
        <Brand />
        <nav className="mt-10 space-y-1 text-sm" aria-label="Primary navigation">
          {NAV.map((item) => (
            <NavLink
              key={item.href}
              href={item.href}
              label={item.label}
              icon={item.icon}
              active={pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href))}
            />
          ))}
        </nav>
        <div className="mt-auto space-y-3">
          <CreditWidget credits={credits} />
          <button onClick={logout} className="flex items-center gap-2 text-xs text-white/45 transition hover:text-white">
            <LogOut className="h-3.5 w-3.5" />Log out
          </button>
        </div>
      </aside>

      <div className="relative">
        <header className="sticky top-0 z-20 flex min-h-20 items-center justify-between gap-4 border-b border-white/[.07] bg-[#07080f]/90 px-5 py-3 backdrop-blur-xl sm:px-8">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-[.16em] text-white/35">{eyebrow}</p>
            <h1 className="mt-1 truncate text-xl font-semibold">{title}</h1>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            {actions}
            <button aria-label="Notifications" className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 text-white/55 transition hover:text-white"><Bell className="h-4 w-4" /></button>
            <UserMenu />
          </div>
        </header>
        {/* Content re-animates on each route change (keyed by pathname) so
            navigating between workspace pages has a subtle, consistent entrance. */}
        <motion.div
          key={pathname}
          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
        >
          {children}
        </motion.div>
      </div>
    </main>
  );
}
