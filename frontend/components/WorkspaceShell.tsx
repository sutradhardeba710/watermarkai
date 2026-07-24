"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { Bell, CreditCard, FolderKanban, Inbox, LogOut, Menu, Sparkles, Upload, Zap } from "lucide-react";
import { useState } from "react";

import { useAuthStore } from "@/features/auth/authStore";
import { authApi } from "@/services/auth";
import { paymentsApi, type CreditStatus } from "@/services/payments";
import { UserMenu } from "@/features/account/UserMenu";
import { Sheet, SheetClose, SheetContent, SheetTitle } from "@/components/ui/sheet";

function Brand() {
  return <Link href="/" className="flex min-h-11 items-center gap-2.5 text-lg font-semibold tracking-tight text-white"><span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] text-white shadow-[0_0_22px_rgba(79,124,255,.35)]"><Sparkles className="h-5 w-5" /></span>ClearFrame</Link>;
}

const NAV = [
  { href: "/dashboard", label: "Projects", icon: FolderKanban },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/billing", label: "Billing", icon: CreditCard },
];

function isActive(pathname: string, href: string) {
  return pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
}

function NavLink({ href, label, icon: Icon, active, onSelect }: { href: string; label: string; icon: typeof FolderKanban; active: boolean; onSelect?: () => void }) {
  return <Link href={href} onClick={onSelect} aria-current={active ? "page" : undefined} className={`relative flex min-h-12 items-center gap-3 rounded-xl px-3 py-2.5 font-medium transition ${active ? "border border-[#4f7cff]/25 bg-gradient-to-r from-[#4f7cff]/15 to-[#8b5cf6]/10 text-white" : "border border-transparent text-white/60 hover:bg-white/5 hover:text-white"}`}>{active && <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-gradient-to-b from-[#4f7cff] to-[#8b5cf6]" />}<Icon className={`h-5 w-5 ${active ? "text-[#9db9ff]" : ""}`} />{label}</Link>;
}

function CreditWidget({ credits }: { credits: CreditStatus | undefined }) {
  if (!credits) return null;
  const pct = credits.credits_per_day > 0 ? Math.min(100, (credits.credits_remaining / credits.credits_per_day) * 100) : 0;
  const barColor = pct < 20 ? "from-rose-500 to-rose-400" : pct < 50 ? "from-amber-400 to-amber-300" : "from-[#4f7cff] to-[#6d5ef7]";
  return <Link href="/billing" className="block rounded-2xl border border-white/10 bg-white/[.03] p-4 transition hover:border-white/20"><div className="flex items-center justify-between text-xs"><span className="flex items-center gap-1.5 font-medium text-cyan-200"><Zap className="h-4 w-4" />{credits.plan_name}</span><span className="text-white/60">{credits.credits_remaining.toLocaleString("en-IN")} cr</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10"><div className={`h-full rounded-full bg-gradient-to-r ${barColor}`} style={{ width: `${pct}%` }} /></div><p className="mt-2 text-xs text-white/45">{credits.credits_remaining} / {credits.credits_per_day} credits today</p></Link>;
}

type WorkspaceShellProps = { children: React.ReactNode; title: string; eyebrow?: string; actions?: React.ReactNode };

export function WorkspaceShell({ children, title, eyebrow = "Workspace", actions }: WorkspaceShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [menuOpen, setMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const clear = useAuthStore((s) => s.clear);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const ready = useAuthStore((s) => !!s.accessToken);
  const { data: credits } = useQuery<CreditStatus>({ queryKey: ["credits"], queryFn: paymentsApi.credits, enabled: ready });

  async function logout() {
    await authApi.logout(refreshToken ?? undefined);
    clear();
    router.replace("/login");
  }

  return <main className="min-h-dvh bg-[#07080f] pb-[calc(4.5rem+env(safe-area-inset-bottom))] text-[#f5f6fa] lg:pl-64 lg:pb-0">
    <div className="pointer-events-none fixed left-1/2 top-0 z-0 h-96 w-[60rem] max-w-full -translate-x-1/2 bg-[radial-gradient(ellipse_at_top,rgba(79,124,255,.08),transparent_65%)]" />
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-white/[.07] bg-[#0a0c18] px-4 py-6 lg:flex"><Brand /><nav className="mt-10 space-y-1 text-sm" aria-label="Primary navigation">{NAV.map((item) => <NavLink key={item.href} {...item} active={isActive(pathname, item.href)} />)}</nav><div className="mt-auto space-y-3"><CreditWidget credits={credits} /><button onClick={logout} className="flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-sm text-white/50 transition hover:bg-white/5 hover:text-white"><LogOut className="h-4 w-4" />Log out</button></div></aside>

    <Sheet open={menuOpen} onOpenChange={setMenuOpen}><SheetContent side="right" className="w-[min(90vw,22rem)] px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-[max(1.25rem,env(safe-area-inset-top))]"><SheetTitle className="sr-only">Workspace navigation</SheetTitle><Brand /><nav className="mt-8 space-y-1" aria-label="Mobile workspace navigation">{NAV.map((item) => <SheetClose asChild key={item.href}><NavLink {...item} active={isActive(pathname, item.href)} /></SheetClose>)}</nav><div className="mt-auto space-y-3 pt-8"><CreditWidget credits={credits} /><button onClick={logout} className="flex min-h-12 w-full items-center gap-3 rounded-xl px-3 text-sm text-rose-300 hover:bg-rose-400/10"><LogOut className="h-5 w-5" />Log out</button></div></SheetContent></Sheet>

    <Sheet open={notificationsOpen} onOpenChange={setNotificationsOpen}><SheetContent side="bottom" className="px-5 pb-[calc(1.25rem+env(safe-area-inset-bottom))] pt-6"><SheetTitle className="text-lg font-semibold">Notifications</SheetTitle><div className="grid min-h-44 place-items-center text-center"><div><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-white/5 text-white/45"><Inbox className="h-6 w-6" /></span><p className="mt-4 font-medium">You’re all caught up</p><p className="mt-1 text-sm text-white/50">Project and billing updates will appear here.</p></div></div></SheetContent></Sheet>

    <div className="relative"><header className="sticky top-0 z-20 flex min-h-[4.5rem] items-center justify-between gap-3 border-b border-white/[.07] bg-[#07080f]/90 px-4 py-3 pt-[max(.75rem,env(safe-area-inset-top))] backdrop-blur-xl sm:min-h-20 sm:px-8"><div className="flex min-w-0 items-center gap-2"><button type="button" aria-label="Open workspace navigation" onClick={() => setMenuOpen(true)} className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-white/10 text-white/70 lg:hidden"><Menu className="h-5 w-5" /></button><div className="min-w-0"><p className="hidden text-xs uppercase tracking-[.16em] text-white/40 sm:block">{eyebrow}</p><h1 className="truncate text-lg font-semibold sm:mt-1 sm:text-xl">{title}</h1></div></div><div className="flex shrink-0 items-center gap-2 sm:gap-3">{actions}<button type="button" aria-label="Open notifications" onClick={() => setNotificationsOpen(true)} className="grid h-11 w-11 place-items-center rounded-xl border border-white/10 text-white/60 transition hover:text-white"><Bell className="h-5 w-5" /></button><UserMenu /></div></header><motion.div key={pathname} initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}>{children}</motion.div></div>

    <nav aria-label="Mobile workspace navigation" className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-3 border-t border-white/10 bg-[#0a0c18]/95 px-2 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden">{NAV.map(({ href, label, icon: Icon }) => { const active=isActive(pathname, href); return <Link key={href} href={href} aria-current={active ? "page" : undefined} className={`flex min-h-16 flex-col items-center justify-center gap-1 rounded-xl text-xs font-medium ${active ? "text-cyan-200" : "text-white/50"}`}><Icon className="h-5 w-5" />{label}</Link>; })}</nav>
  </main>;
}