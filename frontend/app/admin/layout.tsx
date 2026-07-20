"use client";
// Admin shell: auth guard + permission-aware sidebar. Every /admin/* page
// renders inside this layout. The guard admits role==="admin" (legacy super
// admin) or any user with an admin_role; the server enforces per-route
// permissions regardless.
import { ReactNode, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { useAuthStore } from "@/features/auth/authStore";
import { effectiveAdminRole } from "@/features/admin/permissions";
import { AdminSidebar } from "@/components/admin/AdminSidebar";

export default function AdminLayout({ children }: { children: ReactNode }) {
  useHydrateAuth();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const hydrated = useAuthStore((s) => s.hydrated);
  const token = useAuthStore((s) => s.accessToken);

  useEffect(() => {
    if (!hydrated) return;
    if (!token) router.replace("/login?redirect=%2Fadmin");
    else if (!effectiveAdminRole(user)) router.replace("/dashboard");
  }, [hydrated, token, user, router]);

  if (!hydrated || !token || !effectiveAdminRole(user)) return null;

  return (
    <main className="min-h-dvh bg-[#07080f] text-white lg:pl-64">
      <AdminSidebar />
      <div className="mx-auto max-w-7xl px-5 py-8 sm:px-8">{children}</div>
    </main>
  );
}
