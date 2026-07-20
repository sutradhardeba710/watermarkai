"use client";
// AI model registry (PRD §19). Lists registered model versions grouped by type
// with lifecycle actions (enable testing/production, set default/fallback,
// rollback, disable). The system records the exact model version used for every
// job, so promoting a default here changes what new jobs run — every action is
// audited server-side.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AIModel, ModelAction } from "@/types";
import {
  Badge, DataTable, ErrorNote, LoadingBlock, PageHeader,
} from "@/components/admin/ui";
import { ConfirmActionDialog, ConfirmActionState } from "@/components/admin/ConfirmActionDialog";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

const ACTIONS: { action: ModelAction; label: string; danger?: boolean; reason?: boolean }[] = [
  { action: "enable_testing", label: "Testing" },
  { action: "enable_production", label: "Activate" },
  { action: "set_default", label: "Set default" },
  { action: "set_fallback", label: "Set fallback" },
  { action: "rollback", label: "Roll back", danger: true, reason: true },
  { action: "disable", label: "Disable", danger: true, reason: true },
  { action: "deprecate", label: "Deprecate", danger: true, reason: true },
];

export default function AdminModelsPage() {
  const me = useAuthStore((s) => s.user);
  const canManage = hasPermission(me, "models.manage");
  const qc = useQueryClient();
  const [dialog, setDialog] = useState<ConfirmActionState | null>(null);

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "models"],
    queryFn: () => adminApi.listModels(),
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "models"] });
  }

  function act(model: AIModel, a: (typeof ACTIONS)[number]) {
    setDialog({
      title: a.label,
      description: `${a.label} — ${model.name} v${model.version} (${model.model_type}).`,
      confirmLabel: a.label,
      danger: a.danger,
      requireReason: a.reason,
      onConfirm: async (reason) => {
        await adminApi.actOnModel(model.id, { action: a.action, reason: reason || undefined });
        toast.success(`${model.name}: ${a.label.toLowerCase()} applied.`);
        refresh();
      },
    });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Models"
        title="AI model registry"
        subtitle="Registered model versions, their rollout state, and lifecycle controls."
      />
      {error && <ErrorNote text="Unable to load models." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <DataTable<AIModel>
          rows={data}
          rowKey={(m) => m.id}
          empty="No models registered yet."
          columns={[
            {
              key: "name", header: "Model", render: (m) => (
                <div>
                  <p className="text-sm text-white/85">{m.name} <span className="text-white/40">v{m.version}</span></p>
                  <p className="text-xs text-white/40">{m.model_type}</p>
                </div>
              ),
            },
            { key: "status", header: "Status", render: (m) => <Badge status={m.status} /> },
            {
              key: "flags", header: "Flags", render: (m) => (
                <div className="flex gap-1.5">
                  {m.is_default && <Badge status="default" />}
                  {m.is_fallback && <Badge status="fallback" />}
                </div>
              ),
            },
            {
              key: "rollout", header: "Rollout", render: (m) => (
                <span className="text-xs text-white/55">
                  {m.rollout_strategy}{m.rollout_strategy === "percentage" ? ` ${m.rollout_percentage}%` : ""}
                </span>
              ),
            },
            {
              key: "quality", header: "Quality", render: (m) => (
                <span className="text-xs text-white/55">{m.quality_score != null ? m.quality_score : "—"}</span>
              ),
            },
            {
              key: "actions", header: "", className: "text-right", render: (m) => canManage ? (
                <div className="flex flex-wrap justify-end gap-1.5">
                  {ACTIONS.map((a) => (
                    <button
                      key={a.action}
                      onClick={() => act(m, a)}
                      className={`rounded-lg border px-2.5 py-1 text-[11px] ${
                        a.danger
                          ? "border-rose-400/20 text-rose-300 hover:bg-rose-400/10"
                          : "border-white/10 text-white/65 hover:bg-white/5"
                      }`}
                    >
                      {a.label}
                    </button>
                  ))}
                </div>
              ) : null,
            },
          ]}
        />
      )}
      <ConfirmActionDialog state={dialog} onClose={() => setDialog(null)} />
    </div>
  );
}
