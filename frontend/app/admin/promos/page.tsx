"use client";
// Promo code management (PRD §16). Percentage or flat-amount discounts. Flat
// amounts are entered in ₹ and stored as paise. Sandbox-only codes are blocked
// from production by the server.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AdminPromo } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, PageHeader, formatINR } from "@/components/admin/ui";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

interface PromoForm {
  code: string;
  description: string;
  discount_type: "percentage" | "fixed";
  discount_value: number;
  max_discount_rupees: number | "";
  min_purchase_rupees: number | "";
  max_total_uses: number | "";
  max_uses_per_user: number | "";
  sandbox_only: boolean;
  new_users_only: boolean;
}

function blankForm(): PromoForm {
  return {
    code: "", description: "", discount_type: "percentage", discount_value: 10,
    max_discount_rupees: "", min_purchase_rupees: "", max_total_uses: "",
    max_uses_per_user: "", sandbox_only: false, new_users_only: false,
  };
}

function rupeesToPaise(v: number | ""): number | undefined {
  return v === "" ? undefined : Math.round(Number(v) * 100);
}
function count(v: number | ""): number | undefined {
  return v === "" ? undefined : Number(v);
}

export default function AdminPromosPage() {
  const me = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const canManage = hasPermission(me, "promos.manage");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<PromoForm>(blankForm());

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "promos"],
    queryFn: () => adminApi.listPromos(),
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "promos"] });
  }

  async function create() {
    if (!form.code.trim()) {
      toast.error("Enter a promo code.");
      return;
    }
    try {
      await adminApi.createPromo({
        code: form.code.trim().toUpperCase(),
        description: form.description || undefined,
        discount_type: form.discount_type,
        discount_value: form.discount_type === "fixed"
          ? Math.round(form.discount_value * 100)
          : Number(form.discount_value),
        max_discount_inr: rupeesToPaise(form.max_discount_rupees),
        min_purchase_inr: rupeesToPaise(form.min_purchase_rupees),
        max_total_uses: count(form.max_total_uses),
        max_uses_per_user: count(form.max_uses_per_user),
        sandbox_only: form.sandbox_only,
        new_users_only: form.new_users_only,
      });
      toast.success("Promo created.");
      setCreating(false);
      setForm(blankForm());
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Create failed.");
    }
  }

  async function toggleActive(p: AdminPromo) {
    try {
      await adminApi.updatePromo(p.id, { is_active: !p.is_active });
      toast.success(p.is_active ? "Promo disabled." : "Promo enabled.");
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Update failed.");
    }
  }

  function discountLabel(p: AdminPromo): string {
    if (p.discount_type === "flat" && p.discount_value != null) return formatINR(p.discount_value);
    return `${p.discount_percent}%`;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Finance"
        title="Promo codes"
        subtitle="Discount codes for checkout, with usage caps and eligibility rules."
        actions={canManage ? (
          <button onClick={() => { setForm(blankForm()); setCreating(true); }} className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-2 text-sm font-semibold text-white">
            New promo
          </button>
        ) : null}
      />
      {error && <ErrorNote text="Unable to load promo codes." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <DataTable<AdminPromo>
          rows={data}
          rowKey={(p) => p.id}
          empty="No promo codes defined."
          columns={[
            {
              key: "code", header: "Code", render: (p) => (
                <div>
                  <p className="font-mono text-sm font-medium text-white">{p.code}</p>
                  {p.description && <p className="text-xs text-white/40">{p.description}</p>}
                </div>
              ),
            },
            { key: "discount", header: "Discount", render: (p) => <span className="text-white/80">{discountLabel(p)}</span> },
            {
              key: "usage", header: "Used", render: (p) => (
                <span className="text-white/70">
                  {p.times_redeemed}
                  {p.max_total_uses != null && <span className="text-white/40">/{p.max_total_uses}</span>}
                </span>
              ),
            },
            {
              key: "flags", header: "Flags", render: (p) => (
                <div className="flex flex-wrap gap-1">
                  {p.sandbox_only && <Badge status="sandbox" />}
                  {p.new_users_only && <Badge status="new_users" />}
                </div>
              ),
            },
            { key: "state", header: "State", render: (p) => <Badge status={p.is_active ? "active" : "disabled"} /> },
            {
              key: "actions", header: "", className: "text-right", render: (p) =>
                canManage ? (
                  <button onClick={() => toggleActive(p)} className="rounded-lg border border-white/10 px-2.5 py-1 text-xs text-white/70 hover:bg-white/5">
                    {p.is_active ? "Disable" : "Enable"}
                  </button>
                ) : null,
            },
          ]}
        />
      )}

      {creating && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4 backdrop-blur-sm" onClick={() => setCreating(false)}>
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-lg space-y-4 rounded-2xl border border-white/10 bg-[#10121f] p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-white">New promo code</h3>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm text-white/75">Code
                <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 font-mono text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">Type
                <select value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value as PromoForm["discount_type"] })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-[#0c0e1a] px-3 text-sm text-white outline-none focus:border-[#4f7cff]">
                  <option value="percentage">Percent (%)</option>
                  <option value="fixed">Flat (₹)</option>
                </select>
              </label>
              <label className="col-span-2 text-sm text-white/75">Description
                <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">{form.discount_type === "fixed" ? "Discount (₹)" : "Discount (%)"}
                <input type="number" min={0} value={form.discount_value} onChange={(e) => setForm({ ...form, discount_value: Number(e.target.value) })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">Max discount (₹)
                <input type="number" min={0} value={form.max_discount_rupees} onChange={(e) => setForm({ ...form, max_discount_rupees: e.target.value === "" ? "" : Number(e.target.value) })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">Min purchase (₹)
                <input type="number" min={0} value={form.min_purchase_rupees} onChange={(e) => setForm({ ...form, min_purchase_rupees: e.target.value === "" ? "" : Number(e.target.value) })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">Max total uses
                <input type="number" min={0} value={form.max_total_uses} onChange={(e) => setForm({ ...form, max_total_uses: e.target.value === "" ? "" : Number(e.target.value) })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">Max uses / user
                <input type="number" min={0} value={form.max_uses_per_user} onChange={(e) => setForm({ ...form, max_uses_per_user: e.target.value === "" ? "" : Number(e.target.value) })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <div className="col-span-2 flex gap-4 text-sm text-white/75">
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.sandbox_only} onChange={(e) => setForm({ ...form, sandbox_only: e.target.checked })} /> Sandbox only</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.new_users_only} onChange={(e) => setForm({ ...form, new_users_only: e.target.checked })} /> New users only</label>
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <button onClick={() => setCreating(false)} className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white/70 hover:bg-white/5">Cancel</button>
              <button onClick={create} className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-2 text-sm font-semibold text-white">Create</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
