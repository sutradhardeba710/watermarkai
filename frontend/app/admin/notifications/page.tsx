"use client";
// Notifications (PRD §23). Two panes: editable email/in-app templates with a
// live variable-fill preview, and a broadcast composer that fans a message out
// to a chosen user segment. Editing/sending requires notifications.manage.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { BroadcastKind, BroadcastTarget, NotificationTemplate, TemplatePreview } from "@/types";
import { Badge, ErrorNote, LoadingBlock, PageHeader } from "@/components/admin/ui";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

const BROADCAST_KINDS: BroadcastKind[] = ["in_app", "maintenance", "feature", "billing", "policy"];
const BROADCAST_TARGETS: BroadcastTarget[] = [
  "all", "specific_plan", "active_subscribers", "free_users", "selected_users", "users_with_active_jobs",
];

export default function AdminNotificationsPage() {
  const me = useAuthStore((s) => s.user);
  const canManage = hasPermission(me, "notifications.manage");
  const qc = useQueryClient();

  const [selected, setSelected] = useState<NotificationTemplate | null>(null);
  const [preview, setPreview] = useState<TemplatePreview | null>(null);

  const templates = useQuery({
    queryKey: ["admin", "notifications", "templates"],
    queryFn: () => adminApi.listTemplates(),
  });

  async function saveTemplate() {
    if (!selected) return;
    try {
      await adminApi.updateTemplate(selected.id, {
        subject: selected.subject,
        html_content: selected.html_content,
        text_content: selected.text_content,
        enabled: selected.enabled,
      });
      toast.success("Template saved.");
      qc.invalidateQueries({ queryKey: ["admin", "notifications", "templates"] });
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Could not save template.");
    }
  }

  async function runPreview() {
    if (!selected) return;
    try {
      const sampleVars = Object.fromEntries((selected.variables || []).map((v) => [v, `<${v}>`]));
      setPreview(await adminApi.previewTemplate(selected.id, sampleVars));
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Could not render preview.");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Notifications"
        title="Templates & broadcasts"
        subtitle="Edit transactional templates and send announcements to a user segment."
      />

      <section className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">Templates</h2>
          {templates.error && <ErrorNote text="Unable to load templates." />}
          {templates.isLoading || !templates.data ? (
            <LoadingBlock />
          ) : templates.data.length === 0 ? (
            <p className="text-sm text-white/40">No templates seeded yet.</p>
          ) : (
            <div className="space-y-1.5">
              {templates.data.map((t) => (
                <button
                  key={t.id}
                  onClick={() => { setSelected(t); setPreview(null); }}
                  className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left text-sm ${
                    selected?.id === t.id
                      ? "border-[#4f7cff]/40 bg-[#4f7cff]/10 text-white"
                      : "border-white/10 text-white/70 hover:bg-white/5"
                  }`}
                >
                  <span className="truncate">{t.name}</span>
                  {!t.enabled && <Badge status="disabled" />}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-white/10 bg-[#10121f] p-5">
          {!selected ? (
            <p className="text-sm text-white/40">Select a template to edit.</p>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-white/85">{selected.name}</p>
                  <p className="font-mono text-xs text-white/35">{selected.key} · v{selected.version}</p>
                </div>
                {selected.variables && selected.variables.length > 0 && (
                  <p className="text-xs text-white/40">Vars: {selected.variables.join(", ")}</p>
                )}
              </div>
              <label className="block text-sm text-white/75">
                Subject
                <input
                  value={selected.subject}
                  onChange={(e) => setSelected({ ...selected, subject: e.target.value })}
                  disabled={!canManage}
                  className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
                />
              </label>
              <label className="block text-sm text-white/75">
                HTML content
                <textarea
                  value={selected.html_content}
                  onChange={(e) => setSelected({ ...selected, html_content: e.target.value })}
                  disabled={!canManage}
                  rows={6}
                  className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 font-mono text-xs text-white outline-none focus:border-[#4f7cff]"
                />
              </label>
              <label className="block text-sm text-white/75">
                Plain-text content
                <textarea
                  value={selected.text_content}
                  onChange={(e) => setSelected({ ...selected, text_content: e.target.value })}
                  disabled={!canManage}
                  rows={3}
                  className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 font-mono text-xs text-white outline-none focus:border-[#4f7cff]"
                />
              </label>
              <div className="flex gap-2">
                <button onClick={runPreview} className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white/70 hover:bg-white/5">
                  Preview
                </button>
                {canManage && (
                  <button onClick={saveTemplate} className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-2 text-sm font-semibold text-white">
                    Save template
                  </button>
                )}
              </div>
              {preview && (
                <div className="space-y-2 rounded-xl border border-white/10 bg-white/[.03] p-4">
                  <p className="text-xs uppercase tracking-wide text-white/40">Preview</p>
                  <p className="text-sm font-medium text-white/85">{preview.subject}</p>
                  <div className="rounded-lg border border-white/10 bg-white p-3 text-sm text-black" dangerouslySetInnerHTML={{ __html: preview.html_content }} />
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {canManage && <BroadcastComposer />}
    </div>
  );
}

function BroadcastComposer() {
  const [kind, setKind] = useState<BroadcastKind>("in_app");
  const [target, setTarget] = useState<BroadcastTarget>("all");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [targetPlan, setTargetPlan] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    if (!title.trim() || !message.trim()) {
      toast.error("Title and message are required.");
      return;
    }
    setBusy(true);
    try {
      const res = await adminApi.sendBroadcast({
        kind, title, message, target,
        target_plan: target === "specific_plan" ? targetPlan : undefined,
      });
      toast.success(`Broadcast sent to ${res.recipient_count} user(s).`);
      setTitle("");
      setMessage("");
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Could not send broadcast.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-4 rounded-2xl border border-white/10 bg-[#10121f] p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-white/50">Broadcast</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm text-white/75">
          Kind
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as BroadcastKind)}
            className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0c0e1a] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
          >
            {BROADCAST_KINDS.map((k) => <option key={k} value={k}>{k.replaceAll("_", " ")}</option>)}
          </select>
        </label>
        <label className="block text-sm text-white/75">
          Target segment
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value as BroadcastTarget)}
            className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0c0e1a] px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
          >
            {BROADCAST_TARGETS.map((t) => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}
          </select>
        </label>
        {target === "specific_plan" && (
          <label className="block text-sm text-white/75">
            Plan id
            <input
              value={targetPlan}
              onChange={(e) => setTargetPlan(e.target.value)}
              className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
            />
          </label>
        )}
      </div>
      <label className="block text-sm text-white/75">
        Title
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
        />
      </label>
      <label className="block text-sm text-white/75">
        Message
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={3}
          className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-[#4f7cff]"
        />
      </label>
      <button
        onClick={send}
        disabled={busy}
        className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
      >
        {busy ? "Sending..." : "Send broadcast"}
      </button>
    </section>
  );
}
