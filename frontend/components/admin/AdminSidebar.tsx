"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Loader2, LogOut, Sparkles, Upload } from "lucide-react";
import { useAuthStore } from "@/features/auth/authStore";
import { NAV_ITEMS, hasPermission, effectiveAdminRole, ROLE_LABELS } from "@/features/admin/permissions";
import { GlobalSearch } from "@/components/admin/GlobalSearch";
import { authApi } from "@/services/auth";

export function AdminSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const user = useAuthStore((s) => s.user);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const clear = useAuthStore((s) => s.clear);
  const role = effectiveAdminRole(user);
  const visible = NAV_ITEMS.filter((item) => hasPermission(user, item.permission));

  async function logout() {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    await authApi.logout(refreshToken ?? undefined);
    clear();
    router.replace("/login");
  }

  return (
    <aside className="fixed inset-y-0 left-0 hidden w-64 overflow-y-auto border-r border-white/[.07] bg-[#0a0c18] px-4 py-6 lg:block">
      <Link href="/" className="flex items-center gap-2.5 text-lg font-semibold">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6]">
          <Sparkles className="h-5 w-5" />
        </span>
        ClearFrame
      </Link>
      {role && (
        <p className="mt-3 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/50">
          {ROLE_LABELS[role]}
        </p>
      )}
      <div className="mt-4">
        <GlobalSearch />
      </div>
      <nav className="mt-8 space-y-1 text-sm">
        {visible.map(({ href, label, icon: Icon }) => {
          const active = href === "/admin" ? pathname === "/admin" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 ${
                active ? "bg-white/10 text-white" : "text-white/55 hover:bg-white/5"
              }`}
            >
              <Icon className={`h-4 w-4 ${active ? "text-[#9eb4ff]" : ""}`} />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-8 border-t border-white/[.07] pt-4">
        <p className="px-3 text-[11px] uppercase tracking-wide text-white/30">App</p>
        <nav className="mt-2 space-y-1 text-sm">
          <Link href="/upload" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-white/55 hover:bg-white/5">
            <Upload className="h-4 w-4" />
            Upload
          </Link>
          <button
            type="button"
            onClick={logout}
            disabled={isLoggingOut}
            className="flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-left text-white/55 transition hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#9eb4ff] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoggingOut ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <LogOut className="h-4 w-4" aria-hidden="true" />
            )}
            {isLoggingOut ? "Logging out?" : "Log out"}
          </button>
        </nav>
      </div>
    </aside>
  );
}
