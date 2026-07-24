"use client";
// Processing presets (PRD §20). Lists the named processing profiles (Fast /
// Balanced / High Quality by default) with their model wiring and encoding
// params, and lets an operator enable/disable, set the platform default, or
// create a new preset. Every mutation is audited server-side.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { Preset } from "@/types";
import {
  Badge, DataTable, ErrorNote, LoadingBlock, PageHeader,
} from "@/components/admin/ui";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

const EMPTY: Partial<Preset> & { name: string } = {
  name: "",
  description: "",
  output_resolution: "1080p",
  frame_sampling_rate: 1,
  mask_expansion: 4,
  feathering: 4,
  encoding_codec: "libx264",
  encoding_quality: 80,
  expected_credit_cost: 10,
};

export default function AdminPresetsPage() {
  const me = useAuthStore((s) => s.user);
  const canManage = hasPermission(me, "presets.manage");
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<Partial<Preset> & { name: string }>(EMPTY);
  const [busy, setBusy] = useState(false);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "presets"],
    queryFn: () => adminApi.listPresets(),
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "presets"] });
  }

  async function toggle(preset: Preset) {
    try {
      await adminApi.updatePreset(preset.id, { enabled: !preset.enabled });
      toast.success(`${preset.name} ${preset.enabled ? "disabled" : "enabled"}.`);
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Could not update preset.");
    }
  }

  async function setDefault(preset: Preset) {
    try {
      await adminApi.setDefaultPreset(preset.id);
      toast.success(`${preset.name} is now the default preset.`);
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Could not set default.");
    }
  }

  async function create() {
    if (!form.name.trim()) {
      toast.error("Preset name is required.");
      return;
    }
    setBusy(true);
    try {
      await adminApi.createPreset(form);
      toast.success("Preset created.");
      setCreating(false);
      setForm(EMPTY);
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Could not create preset.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Presets"
        title="Processing presets"
        subtitle="Named profiles that wire detection / tracking / inpainting models to encoding settings."
        actions={canManage ? (
          <button
            onClick={() => setCreating((v) => !v)}
            className="min-h-11 rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-2 text-sm font-semibold text-white"
          >
            {creating ? "Cancel" : "New preset"}
          </button>
        ) : undefined}
      />

      {creating && (
        <section className="grid gap-4 rounded-2xl border border-white/10 bg-[#10121f] p-5 sm:grid-cols-2 lg:grid-cols-3">
          <LabeledInput label="Name" value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
          <LabeledInput label="Description" value={form.description || ""} onChange={(v) => setForm({ ...form, description: v })} />
          <LabeledInput label="Output resolution" value={form.output_resolution || ""} onChange={(v) => setForm({ ...form, output_resolution: v })} />
          <LabeledNumber label="Frame sampling rate" value={form.frame_sampling_rate ?? 1} onChange={(v) => setForm({ ...form, frame_sampling_rate: v })} />
          <LabeledNumber label="Mask expansion" value={form.mask_expansion ?? 0} onChange={(v) => setForm({ ...form, mask_expansion: v })} />
          <LabeledNumber label="Feathering" value={form.feathering ?? 0} onChange={(v) => setForm({ ...form, feathering: v })} />
          <LabeledNumber label="Encoding quality" value={form.encoding_quality ?? 80} onChange={(v) => setForm({ ...form, encoding_quality: v })} />
          <LabeledNumber label="Expected credit cost" value={form.expected_credit_cost ?? 0} onChange={(v) => setForm({ ...form, expected_credit_cost: v })} />
          <div className="flex items-end">
            <button
              onClick={create}
              disabled={busy}
              className="h-11 w-full rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] text-sm font-semibold text-white disabled:opacity-50"
            >
              {busy ? "Creating..." : "Create preset"}
            </button>
          </div>
        </section>
      )}

      {error && <ErrorNote text="Unable to load presets." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <DataTable<Preset>
          rows={data}
          rowKey={(p) => p.id}
          empty="No presets defined yet."
          columns={[
            {
              key: "name", header: "Preset", render: (p) => (
                <div>
                  <p className="text-sm text-white/85">{p.name}</p>
                  <p className="max-w-md truncate text-xs text-white/40">{p.description || "—"}</p>
                </div>
              ),
            },
            {
              key: "state", header: "State", render: (p) => (
                <div className="flex gap-1.5">
                  <Badge status={p.enabled ? "enabled" : "disabled"} />
                  {p.is_default && <Badge status="default" />}
                </div>
              ),
            },
            { key: "plan", header: "Plan", render: (p) => <span className="text-xs text-white/55">{p.required_plan || "any"}</span> },
            { key: "res", header: "Resolution", render: (p) => <span className="text-xs text-white/55">{p.output_resolution || "—"}</span> },
            { key: "cost", header: "Credits", render: (p) => <span className="text-xs text-white/55">{p.expected_credit_cost ?? "—"}</span> },
            {
              key: "actions", header: "", className: "text-right", render: (p) => canManage ? (
                <div className="flex flex-wrap justify-end gap-1.5">
                  <button onClick={() => toggle(p)} className="min-h-11 rounded-lg border border-white/10 px-3 py-2 text-xs text-white/65 hover:bg-white/5">
                    {p.enabled ? "Disable" : "Enable"}
                  </button>
                  {!p.is_default && (
                    <button onClick={() => setDefault(p)} className="min-h-11 rounded-lg border border-[#4f7cff]/30 px-3 py-2 text-xs text-[#9db4ff] hover:bg-[#4f7cff]/10">
                      Set default
                    </button>
                  )}
                </div>
              ) : null,
            },
          ]}
        />
      )}
    </div>
  );
}

function LabeledInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block text-sm text-white/75">
      {label}
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
      />
    </label>
  );
}

function LabeledNumber({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <label className="block text-sm text-white/75">
      {label}
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]"
      />
    </label>
  );
}
