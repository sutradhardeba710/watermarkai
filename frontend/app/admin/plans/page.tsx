"use client";
// Plan catalog management (PRD §15). List with create + edit. Prices are entered
// in ₹ and converted to paise before hitting the API.
import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { adminApi } from "@/services/admin";
import type { AdminPlan } from "@/types";
import { Badge, DataTable, ErrorNote, LoadingBlock, PageHeader, formatINR } from "@/components/admin/ui";
import { hasPermission } from "@/features/admin/permissions";
import { useAuthStore } from "@/features/auth/authStore";

const BILLING_INTERVALS = ["monthly", "annual", "quarterly"];

interface PlanForm {
  id: string;
  name: string;
  description: string;
  price_rupees: number;
  credits_per_day: number;
  billing_interval: string;
  monthly_credits: number | "";
  max_upload_mb: number | "";
  max_duration_seconds: number | "";
  concurrent_jobs: number | "";
  is_recommended: boolean;
  api_access: boolean;
}

function blankForm(): PlanForm {
  return {
    id: "", name: "", description: "", price_rupees: 0, credits_per_day: 0,
    billing_interval: "monthly", monthly_credits: "", max_upload_mb: "",
    max_duration_seconds: "", concurrent_jobs: "", is_recommended: false, api_access: false,
  };
}

function formFromPlan(p: AdminPlan): PlanForm {
  return {
    id: p.id, name: p.name, description: p.description || "",
    price_rupees: p.price_inr / 100, credits_per_day: p.credits_per_day,
    billing_interval: p.billing_interval, monthly_credits: p.monthly_credits ?? "",
    max_upload_mb: p.max_upload_mb ?? "", max_duration_seconds: p.max_duration_seconds ?? "",
    concurrent_jobs: p.concurrent_jobs ?? "", is_recommended: p.is_recommended, api_access: p.api_access,
  };
}

export default function AdminPlansPage() {
  const me = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const canManage = hasPermission(me, "plans.manage");
  const [editing, setEditing] = useState<AdminPlan | "new" | null>(null);
  const [form, setForm] = useState<PlanForm>(blankForm());

  const { data, error, isLoading } = useQuery({
    queryKey: ["admin", "plans"],
    queryFn: () => adminApi.listPlans(true),
  });

  function refresh() {
    qc.invalidateQueries({ queryKey: ["admin", "plans"] });
  }

  function startCreate() { setForm(blankForm()); setEditing("new"); }
  function startEdit(p: AdminPlan) { setForm(formFromPlan(p)); setEditing(p); }

  function num(v: number | ""): number | undefined {
    return v === "" ? undefined : Number(v);
  }

  async function save() {
    const price_inr = Math.round(form.price_rupees * 100);
    const shared = {
      name: form.name,
      description: form.description || undefined,
      price_inr,
      credits_per_day: Number(form.credits_per_day),
      billing_interval: form.billing_interval,
      monthly_credits: num(form.monthly_credits),
      max_upload_mb: num(form.max_upload_mb),
      max_duration_seconds: num(form.max_duration_seconds),
      concurrent_jobs: num(form.concurrent_jobs),
      is_recommended: form.is_recommended,
      api_access: form.api_access,
    };
    try {
      if (editing === "new") {
        await adminApi.createPlan({ id: form.id.trim(), ...shared });
        toast.success("Plan created.");
      } else if (editing) {
        await adminApi.updatePlan(editing.id, shared);
        toast.success("Plan updated.");
      }
      setEditing(null);
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Save failed.");
    }
  }

  async function toggleArchive(p: AdminPlan) {
    try {
      await adminApi.updatePlan(p.id, { archived: !p.archived });
      toast.success(p.archived ? "Plan restored." : "Plan archived.");
      refresh();
    } catch (err) {
      toast.error((err as { message?: string })?.message || "Update failed.");
    }
  }

  const sorted = useMemo(() => (data ? [...data].sort((a, b) => a.display_order - b.display_order) : []), [data]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Finance"
        title="Plans"
        subtitle="Subscription plan catalog and per-plan limits."
        actions={canManage ? (
          <button onClick={startCreate} className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-2 text-sm font-semibold text-white">
            New plan
          </button>
        ) : null}
      />
      {error && <ErrorNote text="Unable to load plans." />}
      {isLoading || !data ? (
        <LoadingBlock />
      ) : (
        <DataTable<AdminPlan>
          rows={sorted}
          rowKey={(p) => p.id}
          empty="No plans defined."
          columns={[
            {
              key: "name", header: "Plan", render: (p) => (
                <div>
                  <p className="font-medium text-white">{p.name} {p.is_recommended && <span className="text-[#6d5ef7]">★</span>}</p>
                  <p className="text-xs text-white/40">{p.id}</p>
                </div>
              ),
            },
            { key: "price", header: "Price", render: (p) => <span className="text-white/80">{formatINR(p.price_inr)}<span className="text-white/40">/{p.billing_interval.slice(0, 2)}</span></span> },
            { key: "credits", header: "Credits/day", render: (p) => p.credits_per_day },
            { key: "subs", header: "Subscribers", render: (p) => p.subscriber_count },
            {
              key: "state", header: "State", render: (p) => (
                <div className="flex gap-1">
                  {p.archived ? <Badge status="archived" /> : <Badge status="active" />}
                  {p.api_access && <Badge status="api" />}
                </div>
              ),
            },
            {
              key: "actions", header: "", className: "text-right", render: (p) =>
                canManage ? (
                  <div className="flex justify-end gap-2">
                    <button onClick={() => startEdit(p)} className="rounded-lg border border-white/10 px-2.5 py-1 text-xs text-white/70 hover:bg-white/5">Edit</button>
                    <button onClick={() => toggleArchive(p)} className="rounded-lg border border-white/10 px-2.5 py-1 text-xs text-white/60 hover:bg-white/5">
                      {p.archived ? "Restore" : "Archive"}
                    </button>
                  </div>
                ) : null,
            },
          ]}
        />
      )}

      {/* Create / edit form */}
      {editing && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4 backdrop-blur-sm" onClick={() => setEditing(null)}>
          <div onClick={(e) => e.stopPropagation()} className="w-full max-w-lg space-y-4 rounded-2xl border border-white/10 bg-[#10121f] p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-white">{editing === "new" ? "New plan" : `Edit ${editing.name}`}</h3>
            <div className="grid grid-cols-2 gap-3">
              {editing === "new" && (
                <label className="col-span-2 text-sm text-white/75">Plan ID
                  <input value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
                </label>
              )}
              <label className="col-span-2 text-sm text-white/75">Name
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">Price (₹)
                <input type="number" min={0} value={form.price_rupees} onChange={(e) => setForm({ ...form, price_rupees: Number(e.target.value) })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">Interval
                <select value={form.billing_interval} onChange={(e) => setForm({ ...form, billing_interval: e.target.value })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-[#0c0e1a] px-3 text-sm text-white outline-none focus:border-[#4f7cff]">
                  {BILLING_INTERVALS.map((i) => <option key={i} value={i}>{i}</option>)}
                </select>
              </label>
              <label className="text-sm text-white/75">Credits / day
                <input type="number" min={0} value={form.credits_per_day} onChange={(e) => setForm({ ...form, credits_per_day: Number(e.target.value) })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">Monthly credits
                <input type="number" min={0} value={form.monthly_credits} onChange={(e) => setForm({ ...form, monthly_credits: e.target.value === "" ? "" : Number(e.target.value) })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">Max upload (MB)
                <input type="number" min={0} value={form.max_upload_mb} onChange={(e) => setForm({ ...form, max_upload_mb: e.target.value === "" ? "" : Number(e.target.value) })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <label className="text-sm text-white/75">Concurrent jobs
                <input type="number" min={0} value={form.concurrent_jobs} onChange={(e) => setForm({ ...form, concurrent_jobs: e.target.value === "" ? "" : Number(e.target.value) })} className="mt-1 h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white outline-none focus:border-[#4f7cff]" />
              </label>
              <div className="col-span-2 flex gap-4 text-sm text-white/75">
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.is_recommended} onChange={(e) => setForm({ ...form, is_recommended: e.target.checked })} /> Recommended</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.api_access} onChange={(e) => setForm({ ...form, api_access: e.target.checked })} /> API access</label>
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <button onClick={() => setEditing(null)} className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white/70 hover:bg-white/5">Cancel</button>
              <button onClick={save} className="rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-4 py-2 text-sm font-semibold text-white">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
