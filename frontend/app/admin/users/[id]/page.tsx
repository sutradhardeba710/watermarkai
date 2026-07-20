"use client";
// User detail (PRD §8.3–8.5): header card + action toolbar + tabs.
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AdminUserAction } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, Pagination } from "@/components/admin/ui";
import { ConfirmActionDialog, ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { ADMIN_ROLES, ROLE_LABELS, hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

type Tab = "profile" | "billing" | "credits" | "projects" | "jobs" | "activity" | "notes";
const TABS: { id: Tab; label: string; permission?: string }[] = [
  { id: "profile", label: "Profile" },
  { id: "billing", label: "Subscription & payments", permission: "billing.view" },
  { id: "credits", label: "Credits" },
  { id: "projects", label: "Projects", permission: "projects.view" },
  { id: "jobs", label: "Jobs", permission: "jobs.view" },
  { id: "activity", label: "Activity", permission: "audit.view" },
  { id: "notes", label: "Notes", permission: "notes.view" },
];

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(1)} ${units[i]}`;
}

export default function AdminUserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const me = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("profile");
  const [dialog, setDialog] = useState<ConfirmActionState | null>(null);

  const { data: user, error, isLoading } = useQuery({
    queryKey: ["admin", "user", id],
    queryFn: () => adminApi.getUser(id),
  });

  const visibleTabs = TABS.filter((t) => !t.permission || hasPermission(me, t.permission));

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "user", id] });
    qc.invalidateQueries({ queryKey: ["admin", "user-tab", id] });
  }

  function userAction(action: AdminUserAction, opts: { title: string; description: string; danger?: boolean; requireReason?: boolean }) {
    setDialog({
      title: opts.title,
      description: opts.description,
      confirmLabel: opts.title,
      danger: opts.danger,
      requireReason: opts.requireReason,
      onConfirm: async (reason) => {
        await adminApi.actOnUser(id, action, reason || undefined);
        toast.success(`${opts.title} — done.`);
        refresh();
      },
    });
  }

  function adjustCredits(direction: "credit" | "debit") {
    setDialog({
      title: direction === "credit" ? "Add credits" : "Remove credits",
      description: `${direction === "credit" ? "Add credits to" : "Remove credits from"} ${user?.email}. A reason is required and an immutable ledger entry will be written.`,
      confirmLabel: direction === "credit" ? "Add credits" : "Remove credits",
      danger: direction === "debit",
      requireReason: true,
      numberLabel: "Amount",
      numberDefault: 100,
      onConfirm: async (reason, amount) => {
        await adminApi.adjustUserCredits(id, { amount: amount || 0, direction, reason });
        toast.success("Credits adjusted.");
        refresh();
      },
    });
  }

  if (error) return <ErrorNote text="Unable to load this user." />;
  if (isLoading || !user) return <LoadingBlock />;

  const isStaff = !!user.admin_role || user.role === "admin";

  return (
    <div className="space-y-6">
      <button onClick={() => router.push("/admin/users")} className="text-sm text-[#9eb4ff] hover:text-white">← All users</button>

      {/* Header card */}
      <section className="rounded-2xl border border-white/10 bg-[#10121f] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <span className="grid h-14 w-14 place-items-center rounded-full bg-gradient-to-br from-[#4f7cff]/80 to-[#6d5ef7]/80 text-xl font-semibold">
              {(user.full_name || user.email)[0].toUpperCase()}
            </span>
            <div>
              <h1 className="text-2xl font-semibold">{user.full_name}</h1>
              <p className="text-sm text-white/50">{user.email}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Badge status={user.account_status} />
                {isStaff && <Badge status={user.admin_role || "super_admin"} />}
                <Badge status={user.email_verified ? "verified" : "pending"} />
                <span className="text-xs capitalize text-white/40">{user.plan_name || "Free"} plan</span>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
            <div><p className="text-xl font-semibold">{user.credits_remaining}</p><p className="text-xs text-white/40">Credits</p></div>
            <div><p className="text-xl font-semibold">{user.project_count}</p><p className="text-xs text-white/40">Projects</p></div>
            <div><p className="text-xl font-semibold">{user.job_count}</p><p className="text-xs text-white/40">Jobs</p></div>
            <div><p className="text-xl font-semibold">{formatBytes(user.storage_bytes)}</p><p className="text-xs text-white/40">Storage</p></div>
          </div>
        </div>

        {/* Action toolbar (permission-gated; server enforces regardless) */}
        <div className="mt-5 flex flex-wrap gap-2 border-t border-white/[.07] pt-4">
          {hasPermission(me, "users.support") && (
            <>
              {!user.email_verified && (
                <ActionBtn onClick={() => userAction("verify_email", { title: "Verify email", description: `Mark ${user.email} as verified.` })}>Verify email</ActionBtn>
              )}
              {!user.email_verified && (
                <ActionBtn onClick={() => userAction("resend_verification", { title: "Resend verification", description: `Send a fresh verification email to ${user.email}.` })}>Resend verification</ActionBtn>
              )}
              <ActionBtn onClick={() => userAction("force_password_reset", { title: "Force password reset", description: "Sends a reset email and revokes all active sessions." })}>Force password reset</ActionBtn>
              <ActionBtn onClick={() => userAction("revoke_sessions", { title: "Revoke sessions", description: `Sign ${user.email} out of every device (${user.active_session_count} active).` })}>Revoke sessions</ActionBtn>
            </>
          )}
          {hasPermission(me, "users.credits") && (
            <>
              <ActionBtn tone="emerald" onClick={() => adjustCredits("credit")}>Add credits</ActionBtn>
              <ActionBtn tone="rose" onClick={() => adjustCredits("debit")}>Remove credits</ActionBtn>
            </>
          )}
          {hasPermission(me, "users.plan") && (
            <select
              value={user.plan_id || "free"}
              onChange={(e) => {
                const planId = e.target.value;
                setDialog({
                  title: "Change plan",
                  description: `Move ${user.email} to the ${planId} plan? Daily credits reset to the new plan's allowance.`,
                  confirmLabel: "Change plan",
                  onConfirm: async () => {
                    await adminApi.changeUserPlan(id, planId);
                    toast.success("Plan changed.");
                    refresh();
                  },
                });
              }}
              className="h-8 rounded-lg border border-white/10 bg-[#0c0e1a] px-2 text-xs text-white outline-none focus:border-[#4f7cff]"
            >
              <option value="free">Free</option>
              <option value="starter">Starter</option>
              <option value="pro">Pro</option>
            </select>
          )}
          {hasPermission(me, "users.role") && (
            <select
              value={user.admin_role || (user.role === "admin" ? "super_admin" : "")}
              onChange={(e) => {
                const newRole = e.target.value || null;
                setDialog({
                  title: newRole ? "Change admin role" : "Remove staff access",
                  description: newRole
                    ? `Grant ${user.email} the ${ROLE_LABELS[newRole as keyof typeof ROLE_LABELS] || newRole} role?`
                    : `Remove all admin-panel access from ${user.email}?`,
                  confirmLabel: "Apply",
                  danger: !newRole,
                  onConfirm: async () => {
                    await adminApi.changeUserRole(id, newRole);
                    toast.success("Role updated.");
                    refresh();
                  },
                });
              }}
              className="h-8 rounded-lg border border-white/10 bg-[#0c0e1a] px-2 text-xs text-white outline-none focus:border-[#4f7cff]"
            >
              <option value="">No staff role</option>
              {ADMIN_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </select>
          )}
          {hasPermission(me, "users.manage") && user.account_status === "active" && (
            <ActionBtn tone="rose" onClick={() => userAction("suspend", { title: "Suspend account", description: `${user.email} loses access immediately and all sessions are revoked.`, danger: true, requireReason: true })}>Suspend</ActionBtn>
          )}
          {hasPermission(me, "users.manage") && user.account_status === "suspended" && (
            <ActionBtn tone="emerald" onClick={() => userAction("restore", { title: "Restore account", description: `Reactivate ${user.email}.` })}>Restore</ActionBtn>
          )}
          {hasPermission(me, "users.delete") && user.account_status !== "deleted" && (
            <ActionBtn tone="rose" onClick={() => userAction("delete_account", { title: "Delete account", description: "Soft delete: the account is marked deleted, sessions are revoked, and the user can no longer sign in. Financial and compliance records are retained.", danger: true, requireReason: true })}>Delete account</ActionBtn>
          )}
        </div>
      </section>

      {/* Tabs */}
      <nav className="flex gap-2 overflow-x-auto border-b border-white/10">
        {visibleTabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`whitespace-nowrap border-b-2 px-3 py-3 text-sm font-medium ${tab === t.id ? "border-[#4f7cff] text-white" : "border-transparent text-white/45 hover:text-white"}`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <section>
        {tab === "profile" && <ProfileTab user={user} />}
        {tab === "billing" && <BillingTab userId={id} subscription={user.subscription} />}
        {tab === "credits" && <CreditsTab userId={id} />}
        {tab === "projects" && <ProjectsTab userId={id} />}
        {tab === "jobs" && <JobsTab userId={id} />}
        {tab === "activity" && <ActivityTab userId={id} />}
        {tab === "notes" && <NotesTab userId={id} canManage={hasPermission(me, "notes.manage")} />}
      </section>

      <ConfirmActionDialog state={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}

function ActionBtn({ children, onClick, tone }: { children: React.ReactNode; onClick: () => void; tone?: "emerald" | "rose" }) {
  const cls = tone === "emerald"
    ? "border-emerald-400/20 text-emerald-300 hover:bg-emerald-400/10"
    : tone === "rose"
      ? "border-rose-400/20 text-rose-300 hover:bg-rose-400/10"
      : "border-white/10 text-white/70 hover:bg-white/5";
  return <button onClick={onClick} className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${cls}`}>{children}</button>;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-white/40">{label}</p>
      <p className="mt-1 text-sm text-white/80">{value}</p>
    </div>
  );
}

function ProfileTab({ user }: { user: NonNullable<Awaited<ReturnType<typeof adminApi.getUser>>> }) {
  const { data: sessions } = useQuery({
    queryKey: ["admin", "user-tab", user.id, "sessions"],
    queryFn: () => adminApi.listUserSessions(user.id),
  });
  return (
    <div className="space-y-4">
      <div className="grid gap-4 rounded-2xl border border-white/10 bg-[#10121f] p-5 sm:grid-cols-3">
        <Field label="User ID" value={<span className="font-mono text-xs">{user.id}</span>} />
        <Field label="Registered" value={new Date(user.created_at).toLocaleString()} />
        <Field label="Failed jobs" value={user.failed_job_count} />
        <Field label="Daily limit" value={user.credits_limit ?? "—"} />
        <Field label="Used today" value={user.credits_used_today ?? "—"} />
        <Field label="Active sessions" value={user.active_session_count} />
      </div>
      <h3 className="text-sm font-semibold uppercase tracking-wide text-white/40">Sessions</h3>
      <DataTable
        rows={sessions || []}
        rowKey={(s) => s.id}
        empty="No sessions recorded."
        columns={[
          { key: "created", header: "Created", render: (s) => <span className="text-xs text-white/50">{new Date(s.created_at).toLocaleString()}</span> },
          { key: "expires", header: "Expires", render: (s) => <span className="text-xs text-white/50">{new Date(s.expires_at).toLocaleString()}</span> },
          { key: "agent", header: "Device", render: (s) => <span className="max-w-xs truncate text-xs text-white/55">{s.user_agent || "—"}</span> },
          { key: "state", header: "State", render: (s) => <Badge status={s.revoked ? "revoked" : "active"} /> },
        ]}
      />
    </div>
  );
}

function BillingTab({ userId, subscription }: { userId: string; subscription?: { id: string; plan_id: string; status: string; razorpay_subscription_id?: string | null; current_period_end?: string | null; created_at: string } | null }) {
  const { data: payments } = useQuery({
    queryKey: ["admin", "user-tab", userId, "payments"],
    queryFn: () => adminApi.listUserPayments(userId),
  });
  return (
    <div className="space-y-4">
      {subscription ? (
        <div className="grid gap-4 rounded-2xl border border-white/10 bg-[#10121f] p-5 sm:grid-cols-4">
          <Field label="Plan" value={<span className="capitalize">{subscription.plan_id}</span>} />
          <Field label="Status" value={<Badge status={subscription.status} />} />
          <Field label="Razorpay ID" value={<span className="font-mono text-xs">{subscription.razorpay_subscription_id || "—"}</span>} />
          <Field label="Period ends" value={subscription.current_period_end ? new Date(subscription.current_period_end).toLocaleDateString() : "—"} />
        </div>
      ) : (
        <p className="rounded-2xl border border-white/10 bg-[#10121f] p-5 text-sm text-white/45">No subscription — free plan.</p>
      )}
      <h3 className="text-sm font-semibold uppercase tracking-wide text-white/40">Payments</h3>
      <DataTable
        rows={payments || []}
        rowKey={(p) => p.id}
        empty="No payments recorded."
        columns={[
          { key: "date", header: "Date", render: (p) => <span className="text-xs text-white/50">{new Date(p.created_at).toLocaleString()}</span> },
          { key: "amount", header: "Amount", render: (p) => `₹${(p.amount_inr / 100).toLocaleString("en-IN")}` },
          { key: "status", header: "Status", render: (p) => <Badge status={p.status} /> },
          { key: "method", header: "Method", render: (p) => p.method || "—" },
          { key: "rp", header: "Razorpay ID", render: (p) => <span className="font-mono text-xs text-white/50">{p.razorpay_payment_id || "—"}</span> },
          { key: "desc", header: "Description", render: (p) => <span className="text-xs text-white/55">{p.description || "—"}</span> },
        ]}
      />
    </div>
  );
}

function CreditsTab({ userId }: { userId: string }) {
  const [page, setPage] = useState(1);
  const { data } = useQuery({
    queryKey: ["admin", "user-tab", userId, "transactions", page],
    queryFn: () => adminApi.listUserTransactions(userId, page),
  });
  if (!data) return <LoadingBlock />;
  return (
    <div className="space-y-4">
      <DataTable
        rows={data.items}
        rowKey={(t) => t.id}
        empty="No credit transactions yet."
        columns={[
          { key: "date", header: "Date", render: (t) => <span className="text-xs text-white/50">{new Date(t.created_at).toLocaleString()}</span> },
          { key: "dir", header: "Direction", render: (t) => <Badge status={t.direction} /> },
          { key: "amount", header: "Amount", render: (t) => (t.direction === "credit" ? `+${t.amount}` : `−${t.amount}`) },
          { key: "balance", header: "Balance", render: (t) => `${t.balance_before} → ${t.balance_after}` },
          { key: "source", header: "Source", render: (t) => <span className="text-xs text-white/55">{t.source}</span> },
          { key: "reason", header: "Reason", render: (t) => <span className="max-w-xs truncate text-xs text-white/55">{t.reason || "—"}</span> },
        ]}
      />
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
    </div>
  );
}

function ProjectsTab({ userId }: { userId: string }) {
  const router = useRouter();
  const { data: projects } = useQuery({
    queryKey: ["admin", "user-tab", userId, "projects"],
    queryFn: () => adminApi.listUserProjects(userId),
  });
  return (
    <DataTable
      rows={projects || []}
      rowKey={(p) => p.id}
      onRowClick={(p) => router.push(`/admin/projects/${p.id}`)}
      empty="No projects."
      columns={[
        { key: "title", header: "Project", render: (p) => <span className="font-medium text-white">{p.title}</span> },
        { key: "status", header: "Status", render: (p) => <Badge status={p.status} /> },
        { key: "locked", header: "Locked", render: (p) => (p.locked ? <Badge status="locked" /> : "—") },
        { key: "size", header: "Size", render: (p) => (p.file_size ? formatBytes(p.file_size) : "—") },
        { key: "created", header: "Created", render: (p) => <span className="text-xs text-white/50">{new Date(p.created_at).toLocaleDateString()}</span> },
        { key: "expires", header: "Expires", render: (p) => <span className="text-xs text-white/50">{p.expires_at ? new Date(p.expires_at).toLocaleDateString() : "—"}</span> },
      ]}
    />
  );
}

function JobsTab({ userId }: { userId: string }) {
  const { data: jobs } = useQuery({
    queryKey: ["admin", "user-tab", userId, "jobs"],
    queryFn: () => adminApi.listUserJobs(userId),
  });
  return (
    <DataTable
      rows={jobs || []}
      rowKey={(j) => j.id}
      empty="No jobs."
      columns={[
        { key: "id", header: "Job", render: (j) => <span className="font-mono text-xs">{j.id.slice(0, 8)}</span> },
        { key: "type", header: "Type", render: (j) => j.job_type },
        { key: "status", header: "Status", render: (j) => <Badge status={j.status} /> },
        { key: "attempts", header: "Attempts", render: (j) => j.attempt_count },
        { key: "error", header: "Error", render: (j) => <span className="text-xs text-rose-300">{j.error_code || "—"}</span> },
        { key: "created", header: "Created", render: (j) => <span className="text-xs text-white/50">{new Date(j.created_at).toLocaleString()}</span> },
      ]}
    />
  );
}

function ActivityTab({ userId }: { userId: string }) {
  const [page, setPage] = useState(1);
  const { data } = useQuery({
    queryKey: ["admin", "user-tab", userId, "activity", page],
    queryFn: () => adminApi.listUserActivity(userId, page),
  });
  if (!data) return <LoadingBlock />;
  return (
    <div className="space-y-4">
      <DataTable
        rows={data.items}
        rowKey={(e) => e.id}
        empty="No recorded activity."
        columns={[
          { key: "time", header: "Time", render: (e) => <span className="text-xs text-white/50">{new Date(e.created_at).toLocaleString()}</span> },
          { key: "action", header: "Action", render: (e) => <Badge status={e.action} /> },
          { key: "actor", header: "Actor", render: (e) => <span className="font-mono text-xs text-white/55">{e.actor_id === userId ? "self" : e.actor_id?.slice(0, 8) || "system"}</span> },
          { key: "reason", header: "Reason", render: (e) => <span className="max-w-xs truncate text-xs text-white/55">{e.reason || "—"}</span> },
        ]}
      />
      <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
    </div>
  );
}

function NotesTab({ userId, canManage }: { userId: string; canManage: boolean }) {
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const { data: notes } = useQuery({
    queryKey: ["admin", "user-tab", userId, "notes"],
    queryFn: () => adminApi.listUserNotes(userId),
  });

  async function addNote() {
    if (body.trim().length === 0) return;
    await adminApi.createUserNote(userId, { body: body.trim() });
    setBody("");
    toast.success("Note added.");
    qc.invalidateQueries({ queryKey: ["admin", "user-tab", userId, "notes"] });
  }

  async function removeNote(noteId: string) {
    await adminApi.deleteNote(noteId);
    toast.success("Note deleted.");
    qc.invalidateQueries({ queryKey: ["admin", "user-tab", userId, "notes"] });
  }

  return (
    <div className="space-y-4">
      {canManage && (
        <div className="flex gap-3">
          <input
            value={body}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") addNote(); }}
            placeholder="Add an internal support note…"
            className="h-11 flex-1 rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none placeholder:text-white/30 focus:border-[#4f7cff]"
          />
          <button onClick={addNote} className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 text-sm font-semibold text-white">Add</button>
        </div>
      )}
      <div className="space-y-3">
        {(notes || []).map((n) => (
          <article key={n.id} className="rounded-2xl border border-white/10 bg-[#10121f] p-4">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm leading-6 text-white/75">{n.body}</p>
              {canManage && (
                <button onClick={() => removeNote(n.id)} className="shrink-0 text-xs text-rose-300/70 hover:text-rose-300">Delete</button>
              )}
            </div>
            <p className="mt-2 text-xs text-white/35">By {n.author_id.slice(0, 8)} · {new Date(n.created_at).toLocaleString()}{n.pinned ? " · pinned" : ""}</p>
          </article>
        ))}
        {(notes || []).length === 0 && (
          <p className="rounded-2xl border border-white/10 bg-[#10121f] p-6 text-center text-sm text-white/45">No notes for this user.</p>
        )}
      </div>
    </div>
  );
}
