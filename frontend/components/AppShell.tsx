"use client";

import Link from "next/link";
import { Bell, FolderKanban, Settings, Shield, Sparkles, Upload } from "lucide-react";

import { useAuthStore } from "@/features/auth/authStore";
import { UserMenu } from "@/features/account/UserMenu";

type AppShellProps = {
  children: React.ReactNode;
  title: string;
  eyebrow?: string;
};

export function AppShell({ children, title, eyebrow = "Workspace" }: AppShellProps) {
  const user = useAuthStore((state) => state.user);

  return (
    <main className="min-h-dvh bg-[#07080f] text-[#f5f6fa] lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-white/[.07] bg-[#0a0c18] px-4 py-6 lg:flex">
        <Link href="/" className="flex items-center gap-2.5 text-lg font-semibold tracking-tight">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] shadow-[0_0_22px_rgba(79,124,255,.35)]"><Sparkles className="h-5 w-5" /></span>
          ClearFrame
        </Link>
        <nav className="mt-10 space-y-1 text-sm" aria-label="Primary navigation">
          <Link href="/dashboard" className="flex min-h-11 items-center gap-3 rounded-xl bg-white/10 px-3 py-2.5 font-medium text-white"><FolderKanban className="h-4 w-4 text-[#9eb4ff]" />Projects</Link>
          <Link href="/upload" className="flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-white/55 hover:bg-white/5 hover:text-white"><Upload className="h-4 w-4" />Upload</Link>
          {(user?.role === "admin" || user?.admin_role) && <Link href="/admin" className="flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-white/55 hover:bg-white/5 hover:text-white"><Shield className="h-4 w-4" />Admin</Link>}
          {(user?.role === "admin" || user?.admin_role) && <Link href="/admin/settings" className="flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-white/55 hover:bg-white/5 hover:text-white"><Settings className="h-4 w-4" />Settings</Link>}
        </nav>
        <p className="mt-auto text-xs leading-5 text-white/35">Authorized video cleanup for footage you own or are licensed to edit.</p>
      </aside>
      <div>
        <header className="sticky top-0 z-20 flex min-h-20 items-center justify-between border-b border-white/[.07] bg-[#07080f]/90 px-5 py-3 backdrop-blur-xl sm:px-8">
          <div><p className="text-xs uppercase tracking-[.16em] text-white/35">{eyebrow}</p><h1 className="mt-1 text-xl font-semibold">{title}</h1></div>
          <div className="flex items-center gap-2">
            <button aria-label="Notifications" className="grid h-10 w-10 place-items-center rounded-xl border border-white/10 text-white/55 transition hover:text-white"><Bell className="h-4 w-4" /></button>
            <UserMenu />
          </div>
        </header>
        {children}
      </div>
    </main>
  );
}
