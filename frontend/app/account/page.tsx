"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  BadgeCheck,
  Camera,
  Check,
  KeyRound,
  Loader2,
  Trash2,
  UserRound,
} from "lucide-react";

import { useHydrateAuth } from "@/features/auth/useHydrateAuth";
import { useAuthStore, type AuthUser } from "@/features/auth/authStore";
import { WorkspaceShell } from "@/components/WorkspaceShell";
import { UserAvatar } from "@/features/account/UserAvatar";
import { accountApi, authApi } from "@/services/auth";

const MAX_AVATAR_BYTES = 5 * 1024 * 1024;
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];

/** Read an axios/api error into a user-safe message. */
function errorMessage(err: unknown, fallback: string): string {
  const e = err as { message?: string };
  return e?.message?.trim() || fallback;
}

/** Section wrapper — consistent card chrome for each settings group. */
function Card({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-white/10 bg-white/[.03] p-5 sm:p-6">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-white">{title}</h2>
        {description && <p className="mt-1 text-sm text-white/50">{description}</p>}
      </div>
      {children}
    </section>
  );
}

/** Transient success/error line under a form action. */
function StatusLine({ status }: { status: { kind: "ok" | "err"; text: string } | null }) {
  if (!status) return null;
  return (
    <p
      className={`flex items-center gap-1.5 text-sm ${
        status.kind === "ok" ? "text-emerald-300" : "text-rose-300"
      }`}
    >
      {status.kind === "ok" ? (
        <Check className="h-4 w-4" />
      ) : (
        <AlertTriangle className="h-4 w-4" />
      )}
      {status.text}
    </p>
  );
}

const inputClass =
  "w-full rounded-xl border border-white/10 bg-[#0a0c18] px-3.5 py-2.5 text-sm text-white outline-none transition placeholder:text-white/30 focus:border-[#4f7cff]/60 focus:ring-2 focus:ring-[#4f7cff]/20 disabled:opacity-50";

/* ------------------------------- Profile ------------------------------- */

function ProfileSection({ user }: { user: AuthUser }) {
  const setUser = useAuthStore((s) => s.setUser);
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState(user.full_name);
  const [savingName, setSavingName] = useState(false);
  const [nameStatus, setNameStatus] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [avatarStatus, setAvatarStatus] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  const nameDirty = name.trim() !== user.full_name && name.trim().length > 0;

  async function saveName(e: React.FormEvent) {
    e.preventDefault();
    if (!nameDirty || savingName) return;
    setSavingName(true);
    setNameStatus(null);
    try {
      const updated = await accountApi.updateProfile(name.trim());
      setUser(updated);
      setName(updated.full_name);
      setNameStatus({ kind: "ok", text: "Name updated." });
    } catch (err) {
      setNameStatus({ kind: "err", text: errorMessage(err, "Could not update your name.") });
    } finally {
      setSavingName(false);
    }
  }

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (!file) return;
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setAvatarStatus({ kind: "err", text: "Use a JPEG, PNG, or WebP image." });
      return;
    }
    if (file.size > MAX_AVATAR_BYTES) {
      setAvatarStatus({ kind: "err", text: "Image must be 5 MB or smaller." });
      return;
    }
    setAvatarBusy(true);
    setAvatarStatus(null);
    try {
      const updated = await accountApi.uploadAvatar(file);
      setUser(updated);
      setAvatarStatus({ kind: "ok", text: "Profile picture updated." });
    } catch (err) {
      setAvatarStatus({ kind: "err", text: errorMessage(err, "Upload failed. Try again.") });
    } finally {
      setAvatarBusy(false);
    }
  }

  async function removeAvatar() {
    if (avatarBusy) return;
    setAvatarBusy(true);
    setAvatarStatus(null);
    try {
      const updated = await accountApi.removeAvatar();
      setUser(updated);
      setAvatarStatus({ kind: "ok", text: "Profile picture removed." });
    } catch (err) {
      setAvatarStatus({ kind: "err", text: errorMessage(err, "Could not remove the picture.") });
    } finally {
      setAvatarBusy(false);
    }
  }

  return (
    <Card title="Profile" description="How you appear across ClearFrame.">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
        {/* Avatar */}
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <UserAvatar user={user} size={96} className="ring-2 ring-white/10" />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={avatarBusy}
              aria-label="Change profile picture"
              className="absolute -bottom-2 -right-2 grid h-11 w-11 place-items-center rounded-full border border-white/15 bg-[#0a0c18] text-white/70 transition hover:text-white disabled:opacity-50"
            >
              {avatarBusy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Camera className="h-4 w-4" />
              )}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept={ACCEPTED_TYPES.join(",")}
              onChange={onPickFile}
              className="hidden"
            />
          </div>
          {user.avatar_url && (
            <button
              type="button"
              onClick={removeAvatar}
              disabled={avatarBusy}
              className="text-xs text-white/45 transition hover:text-rose-300 disabled:opacity-50"
            >
              Remove
            </button>
          )}
        </div>

        {/* Name + email */}
        <form onSubmit={saveName} className="flex-1 space-y-4">
          <div>
            <label htmlFor="full_name" className="mb-1.5 block text-sm font-medium text-white/70">
              Display name
            </label>
            <input
              id="full_name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={255}
              disabled={savingName}
              className={inputClass}
              placeholder="Your name"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-white/70">Email</label>
            <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[.02] px-3.5 py-2.5 text-sm text-white/60">
              <span className="truncate">{user.email}</span>
              {user.email_verified && (
                <span className="ml-auto flex shrink-0 items-center gap-1 text-xs text-cyan-300/90">
                  <BadgeCheck className="h-3.5 w-3.5" />
                  Verified
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={!nameDirty || savingName}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] to-[#6d5ef7] px-4 py-2.5 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {savingName && <Loader2 className="h-4 w-4 animate-spin" />}
              Save changes
            </button>
            <StatusLine status={nameStatus} />
          </div>
          <StatusLine status={avatarStatus} />
        </form>
      </div>
    </Card>
  );
}

/* ------------------------------ Password ------------------------------- */

function PasswordSection() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const canSubmit =
    current.length > 0 && next.length >= 8 && confirm.length >= 8 && !saving;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setStatus(null);
    if (next !== confirm) {
      setStatus({ kind: "err", text: "New passwords do not match." });
      return;
    }
    setSaving(true);
    try {
      await accountApi.changePassword(current, next, confirm);
      setStatus({ kind: "ok", text: "Password changed. Other sessions were signed out." });
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (err) {
      setStatus({ kind: "err", text: errorMessage(err, "Could not change your password.") });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card
      title="Password"
      description="Changing your password signs out every other device."
    >
      <form onSubmit={submit} className="max-w-md space-y-4">
        <div>
          <label htmlFor="current_pw" className="mb-1.5 block text-sm font-medium text-white/70">
            Current password
          </label>
          <input
            id="current_pw"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            disabled={saving}
            className={inputClass}
          />
        </div>
        <div>
          <label htmlFor="new_pw" className="mb-1.5 block text-sm font-medium text-white/70">
            New password
          </label>
          <input
            id="new_pw"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            disabled={saving}
            className={inputClass}
          />
          <p className="mt-1 text-xs text-white/35">
            At least 8 characters, with upper, lower, and a number.
          </p>
        </div>
        <div>
          <label htmlFor="confirm_pw" className="mb-1.5 block text-sm font-medium text-white/70">
            Confirm new password
          </label>
          <input
            id="confirm_pw"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            disabled={saving}
            className={inputClass}
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
            Update password
          </button>
          <StatusLine status={status} />
        </div>
      </form>
    </Card>
  );
}

/* ----------------------------- Danger zone ----------------------------- */

function DangerSection() {
  const router = useRouter();
  const clear = useAuthStore((s) => s.clear);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirmDelete(e: React.FormEvent) {
    e.preventDefault();
    if (!password || deleting) return;
    setDeleting(true);
    setError(null);
    try {
      await accountApi.deleteAccount(password);
      // Soft delete succeeded server-side (sessions revoked). Best-effort logout
      // to drop the refresh token, then wipe local state and leave.
      await authApi.logout(refreshToken ?? undefined);
      clear();
      router.replace("/login?deleted=1");
    } catch (err) {
      setError(errorMessage(err, "Could not delete your account."));
      setDeleting(false);
    }
  }

  return (
    <Card
      title="Delete account"
      description="Your account is deactivated and scheduled for removal. Contact support to restore it."
    >
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-2.5 text-sm font-medium text-rose-200 transition hover:bg-rose-500/20"
        >
          <Trash2 className="h-4 w-4" />
          Delete my account
        </button>
      ) : (
        <form onSubmit={confirmDelete} className="max-w-md space-y-4">
          <div className="flex items-start gap-2 rounded-xl border border-rose-400/25 bg-rose-500/10 p-3 text-sm text-rose-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              This deactivates your account and signs you out everywhere. Enter your password to
              confirm.
            </span>
          </div>
          <div>
            <label htmlFor="del_pw" className="mb-1.5 block text-sm font-medium text-white/70">
              Password
            </label>
            <input
              id="del_pw"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={deleting}
              className={inputClass}
            />
          </div>
          {error && (
            <p className="flex items-center gap-1.5 text-sm text-rose-300">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </p>
          )}
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={!password || deleting}
              className="inline-flex items-center gap-2 rounded-xl bg-rose-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-rose-600 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              {deleting ? "Deleting…" : "Permanently delete"}
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setPassword("");
                setError(null);
              }}
              disabled={deleting}
              className="text-sm text-white/55 transition hover:text-white disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </Card>
  );
}

/* ------------------------------- Page ---------------------------------- */

export default function AccountPage() {
  useHydrateAuth();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const hydrated = useAuthStore((s) => s.hydrated);
  const ready = useAuthStore((s) => !!s.accessToken);

  useEffect(() => {
    if (hydrated && !ready) router.replace("/login");
  }, [hydrated, ready, router]);

  if (!ready || !user) {
    return (
      <main className="grid min-h-dvh place-items-center bg-[#07080f] text-white/50">
        <div className="flex items-center gap-3 text-sm">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white/70" />
          {hydrated ? "Redirecting…" : "Loading your account…"}
        </div>
      </main>
    );
  }

  return (
    <WorkspaceShell title="Account settings" eyebrow="Account">
      <div className="mx-auto max-w-3xl space-y-5 px-5 py-8 sm:px-8">
        <div className="flex items-center gap-2 text-sm text-white/45">
          <UserRound className="h-4 w-4" />
          Manage your profile, security, and account.
        </div>
        <ProfileSection user={user} />
        <PasswordSection />
        <DangerSection />
      </div>
    </WorkspaceShell>
  );
}
