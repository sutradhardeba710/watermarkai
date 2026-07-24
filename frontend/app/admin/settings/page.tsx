"use client";
// Application settings (ADMIN-005 / PRD §26).
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { SystemConfig } from "@/types";
import { ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

export default function AdminSettingsPage() {
  const user = useAuthStore((s) => s.user);
  const canManage = hasPermission(user, "config.manage");
  const [cfg, setCfg] = useState<SystemConfig | null>(null);
  const [form, setForm] = useState<Partial<SystemConfig>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi.getConfig().then((c) => { setCfg(c); setForm(c); }).catch(() => setError("Unable to load system settings."));
  }, []);

  function update<K extends keyof SystemConfig>(key: K, value: SystemConfig[K]) {
    setForm((v) => ({ ...v, [key]: value }));
    setDirty(true);
    setMessage("");
  }

  async function save() {
    setSaving(true);
    setError("");
    try {
      const next = await adminApi.updateConfig(form);
      setCfg(next);
      setForm(next);
      setDirty(false);
      setMessage("Settings saved successfully.");
      toast.success("Settings saved.");
    } catch {
      setError("Settings could not be saved. Check the values and try again.");
    } finally {
      setSaving(false);
    }
  }

  if (error && !cfg) return <ErrorNote text={error} />;
  if (!cfg) return <LoadingBlock />;

  const number = (label: string, key: keyof SystemConfig, help: string) => (
    <label className="block">
      <span className="text-sm font-medium text-white/80">{label}</span>
      <span className="mt-1 block text-xs text-white/40">{help}</span>
      <input
        type="number"
        value={Number(form[key] ?? 0)}
        disabled={!canManage}
        onChange={(e) => update(key, Number(e.target.value) as SystemConfig[typeof key])}
        className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff] focus:ring-2 focus:ring-[#4f7cff]/30 disabled:opacity-50"
      />
    </label>
  );

  return (
    <div className="space-y-6 pb-24">
      <PageHeader
        eyebrow="Platform controls"
        title="Application settings"
        subtitle="Changes apply to new uploads and queued work. Existing jobs keep their current settings."
      />
      {!canManage && (
        <p className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/50">
          Read-only view — your role cannot modify settings.
        </p>
      )}
      <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
        <h3 className="font-semibold">Upload limits</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          {number("Max file size (MB)", "max_file_size_mb", "Maximum upload size allowed per video.")}
          {number("Max duration (seconds)", "max_duration_seconds", "Maximum video length accepted.")}
          {number("Max FPS", "max_fps", "Maximum source frame rate.")}
        </div>
      </section>
      <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
        <h3 className="font-semibold">Video constraints</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {number("Max width (px)", "max_width", "Maximum output width.")}
          {number("Max height (px)", "max_height", "Maximum output height.")}
        </div>
      </section>
      <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
        <h3 className="font-semibold">Workers & retention</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          {number("Worker concurrency", "worker_concurrency", "Tasks handled by each worker.")}
          {number("Max retries", "max_retries", "Automatic retry attempts.")}
          {number("Output retention (days)", "retain_output_days", "How long completed outputs remain available.")}
          {number("Original retention (hours)", "retain_original_hours", "How long original uploads are retained.")}
          {number("Preview retention (hours)", "retain_preview_hours", "How long previews are retained.")}
          {number("Failed retention (hours)", "retain_failed_hours", "How long failed artifacts are retained.")}
        </div>
      </section>
      <section className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
        <h3 className="font-semibold">Formats & models</h3>
        <p className="mt-1 text-xs text-white/40">Comma-separated tags. Example: mp4, mov, webm.</p>
        <label className="mt-4 block text-sm text-white/75">
          Allowed upload extensions
          <input
            value={(form.allowed_upload_extensions || []).join(", ")}
            disabled={!canManage}
            onChange={(e) => update("allowed_upload_extensions", e.target.value.split(",").map((x) => x.trim()).filter(Boolean))}
            className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff] disabled:opacity-50"
          />
        </label>
        <label className="mt-4 block text-sm text-white/75">
          Enabled models
          <input
            value={(form.enabled_models || []).join(", ")}
            disabled={!canManage}
            onChange={(e) => update("enabled_models", e.target.value.split(",").map((x) => x.trim()).filter(Boolean))}
            className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff] disabled:opacity-50"
          />
        </label>
      </section>
      <section className="rounded-2xl border border-amber-400/20 bg-amber-500/[.06] p-5">
        <h3 className="font-semibold text-amber-100">Maintenance</h3>
        <p className="mt-1 text-sm leading-6 text-white/50">Maintenance windows, visitor messaging, and administrator access are managed in one authoritative place.</p>
        <a href="/admin/maintenance" className="mt-4 inline-flex min-h-11 items-center rounded-xl border border-amber-300/20 bg-amber-300/10 px-4 py-2 text-sm font-medium text-amber-100 transition hover:bg-amber-300/15">Open maintenance controls</a>
      </section>
      {(dirty || message || error) && canManage && (
        <div className="sticky bottom-4 flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-[#0c0e1a]/95 p-4 shadow-2xl backdrop-blur-xl">
          <span className="text-sm text-white/60">{message || error || "You have unsaved changes."}</span>
          <button
            onClick={save}
            disabled={!dirty || saving}
            className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save changes"}
          </button>
        </div>
      )}
    </div>
  );
}
