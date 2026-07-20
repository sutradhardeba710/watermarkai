"use client";
// Administrator management (PRD §28) — super-admin only. Lists staff accounts
// and supports invite + role change / suspend / reactivate / revoke-sessions /
// require-MFA / remove. Destructive actions collect a reason via the confirm
// dialog; the server re-validates every guard (self-target, last super-admin).
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AdminListItem, AdminMgmtAction } from "@/types";
import { Badge, ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";
import { ConfirmActionDialog, type ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { ADMIN_ROLES, ROLE_LABELS, hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

export default function AdminAdministratorsPage() {
  const me = useAuthStore((s) => s.user);
  const canManage = hasPermission(me, "admins.manage");
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState<ConfirmActionState | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "administrators"],
    queryFn: () => adminApi.listAdministrators(),
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "administrators"] });
  }

  async function runAction(admin: AdminListItem, action: AdminMgmtAction, reason?: string, newRole?: string) {
    try {
      await adminApi.actOnAdministrator(admin.id, { action, reason, new_role: newRole });
      toast.success(`${admin.email}: ${action.replace(/_/g, " ")} applied.`);
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Action failed.");
    }
  }

  function askDestructive(admin: AdminListItem, action: AdminMgmtAction, label: string) {
    setConfirm({
      title: `${label} — ${admin.email}`,
      description: `This will ${label.toLowerCase()} the administrator account for ${admin.full_name}.`,
      confirmLabel: label,
      requireReason: true,
      danger: true,
      onConfirm: (reason) => runAction(admin, action, reason),
    });
  }

  function changeRole(admin: AdminListItem, newRole: string) {
    if (newRole === (admin.admin_role || "")) return;
    runAction(admin, "change_role", undefined, newRole);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Access"
        title="Administrators"
        subtitle="Staff accounts and their panel roles. Super-admin only (§28)."
        actions={
          canManage && (
            <button
              onClick={() => setInviteOpen(true)}
              className="rounded-lg bg-[#4f7cff] px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[#4f7cff]/85"
            >
              Invite admin
            </button>
          )
        }
      />
      {error && <ErrorNote text="Unable to load administrators." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <div className="space-y-2">
          {data.map((admin) => {
            const isSelf = admin.id === me?.id;
            return (
              <div key={admin.id} className="rounded-xl border border-white/10 bg-[#10121f] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-white/85">
                      {admin.full_name}{" "}
                      {isSelf && <span className="text-xs text-white/35">(you)</span>}
                    </p>
                    <p className="text-xs text-white/45">{admin.email}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge status={admin.account_status} />
                    {admin.mfa_enabled && (
                      <span className="rounded-md bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300">MFA</span>
                    )}
                    {canManage && !isSelf ? (
                      <select
                        value={admin.admin_role || ""}
                        onChange={(e) => changeRole(admin, e.target.value)}
                        className="rounded-lg border border-white/10 bg-[#0c0e1a] px-2 py-1 text-xs text-white/80"
                      >
                        {ADMIN_ROLES.map((r) => (
                          <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                        ))}
                      </select>
                    ) : (
                      <span className="rounded-md bg-white/5 px-2 py-0.5 text-xs text-white/60">
                        {admin.admin_role ? ROLE_LABELS[admin.admin_role as keyof typeof ROLE_LABELS] ?? admin.admin_role : "—"}
                      </span>
                    )}
                  </div>
                </div>
                {canManage && !isSelf && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {admin.account_status === "active" ? (
                      <button
                        onClick={() => askDestructive(admin, "suspend", "Suspend")}
                        className="rounded-lg border border-white/10 bg-[#0c0e1a] px-2.5 py-1 text-xs text-amber-300 hover:text-amber-200"
                      >
                        Suspend
                      </button>
                    ) : (
                      <button
                        onClick={() => runAction(admin, "reactivate")}
                        className="rounded-lg border border-white/10 bg-[#0c0e1a] px-2.5 py-1 text-xs text-emerald-300 hover:text-emerald-200"
                      >
                        Reactivate
                      </button>
                    )}
                    <button
                      onClick={() => runAction(admin, "revoke_sessions")}
                      className="rounded-lg border border-white/10 bg-[#0c0e1a] px-2.5 py-1 text-xs text-white/70 hover:text-white"
                    >
                      Revoke sessions
                    </button>
                    <button
                      onClick={() => runAction(admin, "require_mfa")}
                      className="rounded-lg border border-white/10 bg-[#0c0e1a] px-2.5 py-1 text-xs text-white/70 hover:text-white"
                    >
                      Require MFA
                    </button>
                    <button
                      onClick={() => askDestructive(admin, "remove", "Remove")}
                      className="rounded-lg border border-white/10 bg-[#0c0e1a] px-2.5 py-1 text-xs text-red-300 hover:text-red-200"
                    >
                      Remove
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      <ConfirmActionDialog state={confirm} onClose={() => setConfirm(null)} />
      {inviteOpen && (
        <InviteDialog
          onClose={() => setInviteOpen(false)}
          onDone={() => {
            setInviteOpen(false);
            refresh();
          }}
        />
      )}
    </div>
  );
}

function InviteDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<string>("support");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function submit() {
    if (!email.includes("@") || fullName.trim().length < 1) {
      setErr("A valid email and name are required.");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      await adminApi.inviteAdministrator({ email, full_name: fullName, admin_role: role });
      toast.success(`Invited ${email} as ${ROLE_LABELS[role as keyof typeof ROLE_LABELS]}.`);
      onDone();
    } catch (e) {
      setErr((e as { message?: string })?.message || "Invite failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-white/10 bg-[#10121f] p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold text-white/90">Invite administrator</h2>
        <p className="mt-1 text-xs text-white/45">
          They receive a random password and must set one via reset. MFA is required (§28.1).
        </p>
        <div className="mt-4 space-y-3">
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Full name"
            className="w-full rounded-lg border border-white/10 bg-[#0c0e1a] px-3 py-2 text-sm text-white/85 outline-none focus:border-[#4f7cff]"
          />
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            className="w-full rounded-lg border border-white/10 bg-[#0c0e1a] px-3 py-2 text-sm text-white/85 outline-none focus:border-[#4f7cff]"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-[#0c0e1a] px-3 py-2 text-sm text-white/85"
          >
            {ADMIN_ROLES.map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r]}</option>
            ))}
          </select>
          {err && <p className="text-xs text-red-400">{err}</p>}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg px-3 py-1.5 text-sm text-white/60 hover:text-white">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={busy}
            className="rounded-lg bg-[#4f7cff] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            {busy ? "Inviting…" : "Send invite"}
          </button>
        </div>
      </div>
    </div>
  );
}
