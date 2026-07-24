"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Loader2, LogOut, Menu, Sparkles, Upload } from "lucide-react";
import { useAuthStore } from "@/features/auth/authStore";
import { NAV_ITEMS, hasPermission, effectiveAdminRole, ROLE_LABELS } from "@/features/admin/permissions";
import { GlobalSearch } from "@/components/admin/GlobalSearch";
import { authApi } from "@/services/auth";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";

export function AdminSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [open, setOpen] = useState(false);
  const user = useAuthStore((s) => s.user);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const clear = useAuthStore((s) => s.clear);
  const role = effectiveAdminRole(user);
  const visible = NAV_ITEMS.filter((item) => hasPermission(user, item.permission));

  async function logout() { if (isLoggingOut) return; setIsLoggingOut(true); await authApi.logout(refreshToken ?? undefined); clear(); router.replace("/login"); }

  const navigation = <><Link href="/" className="flex min-h-11 items-center gap-2.5 text-lg font-semibold"><span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6]"><Sparkles className="h-5 w-5" /></span>ClearFrame</Link>{role && <p className="mt-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/55">{ROLE_LABELS[role]}</p>}<div className="mt-4"><GlobalSearch /></div><nav className="mt-6 space-y-1 text-sm" aria-label="Admin navigation">{visible.map(({ href,label,icon:Icon }) => { const active=href==="/admin" ? pathname==="/admin" : pathname.startsWith(href); return <Link key={href} href={href} onClick={() => setOpen(false)} aria-current={active ? "page" : undefined} className={`flex min-h-12 items-center gap-3 rounded-xl px-3 py-2.5 ${active ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"}`}><Icon className={`h-5 w-5 ${active ? "text-[#9eb4ff]" : ""}`} />{label}</Link>; })}</nav><div className="mt-8 border-t border-white/[.07] pt-4"><p className="px-3 text-xs uppercase tracking-wide text-white/35">App</p><nav className="mt-2 space-y-1 text-sm"><Link href="/upload" onClick={() => setOpen(false)} className="flex min-h-12 items-center gap-3 rounded-xl px-3 text-white/60 hover:bg-white/5"><Upload className="h-5 w-5" />Upload</Link><button type="button" onClick={logout} disabled={isLoggingOut} className="flex min-h-12 w-full items-center gap-3 rounded-xl px-3 text-left text-white/60 hover:bg-white/5 hover:text-white disabled:opacity-50">{isLoggingOut ? <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" /> : <LogOut className="h-5 w-5" />}{isLoggingOut ? "Logging out…" : "Log out"}</button></nav></div></>;

  return <><header className="sticky top-0 z-30 flex min-h-16 items-center justify-between border-b border-white/10 bg-[#0a0c18]/95 px-4 pt-[env(safe-area-inset-top)] backdrop-blur lg:hidden"><Link href="/admin" className="flex items-center gap-2 font-semibold"><span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] to-[#8b5cf6]"><Sparkles className="h-5 w-5" /></span>Admin</Link><button type="button" aria-label="Open admin navigation" onClick={() => setOpen(true)} className="grid h-11 w-11 place-items-center rounded-xl border border-white/10"><Menu className="h-5 w-5" /></button></header><aside className="fixed inset-y-0 left-0 hidden w-64 overflow-y-auto border-r border-white/[.07] bg-[#0a0c18] px-4 py-6 lg:block">{navigation}</aside><Sheet open={open} onOpenChange={setOpen}><SheetContent side="right" className="w-[min(92vw,22rem)] px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-[max(1.25rem,env(safe-area-inset-top))]"><SheetTitle className="sr-only">Admin navigation</SheetTitle>{navigation}</SheetContent></Sheet></>;
}