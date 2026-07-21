"use client";

import { FormEvent, useMemo, useState } from "react";
import { BadgeDollarSign, BriefcaseBusiness, Check, CircleAlert, FileWarning, LifeBuoy, LoaderCircle, Mail, Wrench } from "lucide-react";

const SUPPORT_EMAIL = "support@clearframe.app";
const categories = [
  { value: "general", label: "General support", description: "Account or product questions", icon: LifeBuoy },
  { value: "billing", label: "Billing help", description: "Plans, payments, or cancellation", icon: BadgeDollarSign },
  { value: "technical", label: "Technical issue", description: "Upload, masking, or processing", icon: Wrench },
  { value: "agency", label: "Agency inquiry", description: "Business and workflow needs", icon: BriefcaseBusiness },
  { value: "compliance", label: "Compliance report", description: "Report possible misuse", icon: FileWarning },
] as const;

type Category = (typeof categories)[number]["value"];
type Errors = Partial<Record<"name" | "email" | "subject" | "message", string>>;

export function ContactForm() {
  const [category, setCategory] = useState<Category>("general");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [reference, setReference] = useState("");
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [phase, setPhase] = useState<"idle" | "opening" | "ready" | "error">("idle");
  const categoryLabel = categories.find((item) => item.value === category)?.label ?? "General support";

  const mailto = useMemo(() => {
    const body = [
      `Category: ${categoryLabel}`,
      `Name: ${name.trim()}`,
      `Reply email: ${email.trim()}`,
      reference.trim() ? `Project or job reference: ${reference.trim()}` : "",
      "",
      message.trim(),
    ].filter(Boolean).join("\n");
    return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`[${categoryLabel}] ${subject.trim()}`)}&body=${encodeURIComponent(body)}`;
  }, [categoryLabel, email, message, name, reference, subject]);

  function validate() {
    const next: Errors = {};
    if (!name.trim()) next.name = "Enter your name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) next.email = "Enter a valid reply email.";
    if (subject.trim().length < 4) next.subject = "Add a short subject.";
    if (message.trim().length < 20) next.message = "Add at least 20 characters so we can understand the request.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPhase("idle");
    if (!validate()) {
      window.requestAnimationFrame(() => document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus());
      return;
    }
    setPhase("opening");
    try {
      window.location.href = mailto;
      window.setTimeout(() => setPhase("ready"), 650);
    } catch {
      setPhase("error");
    }
  }

  const field = "mt-2 min-h-12 w-full rounded-xl border border-white/10 bg-white/[.035] px-4 text-base text-white outline-none transition placeholder:text-white/25 focus:border-cyan-300/50 focus:ring-2 focus:ring-cyan-300/20";

  return <form onSubmit={submit} noValidate className="rounded-[2rem] border border-white/10 bg-[#10121f] p-5 shadow-[0_24px_70px_rgba(0,0,0,.3)] sm:p-8">
    <fieldset>
      <legend className="text-sm font-semibold text-white">Choose a category</legend>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {categories.map(({ value, label, description, icon: Icon }) => <button key={value} type="button" aria-pressed={category === value} onClick={() => setCategory(value)} className={`flex min-h-[76px] items-start gap-3 rounded-2xl border p-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 ${category === value ? "border-[#4f7cff]/55 bg-[#4f7cff]/12" : "border-white/10 bg-white/[.02] hover:border-white/20"}`}>
          <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${category === value ? "bg-[#4f7cff]/20 text-cyan-100" : "bg-white/[.05] text-white/45"}`}><Icon size={16} /></span>
          <span><span className="block text-sm font-semibold text-white">{label}</span><span className="mt-1 block text-xs text-white/40">{description}</span></span>
        </button>)}
      </div>
    </fieldset>

    <div className="mt-7 grid gap-5 sm:grid-cols-2">
      <Field label="Name" error={errors.name}><input value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" aria-invalid={Boolean(errors.name)} aria-describedby={errors.name ? "name-error" : undefined} className={field} /></Field>
      <Field label="Email" error={errors.email}><input value={email} onChange={(event) => setEmail(event.target.value)} type="email" autoComplete="email" aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? "email-error" : undefined} className={field} /></Field>
    </div>
    <Field label="Subject" error={errors.subject} className="mt-5"><input value={subject} onChange={(event) => setSubject(event.target.value)} aria-invalid={Boolean(errors.subject)} aria-describedby={errors.subject ? "subject-error" : undefined} className={field} /></Field>
    <label className="mt-5 block"><span className="text-sm font-medium text-white/70">Project or job reference <span className="text-white/35">(optional)</span></span><input value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Project ID, job ID, or payment reference" className={field} /></label>
    <Field label="Message" error={errors.message} className="mt-5"><textarea value={message} onChange={(event) => setMessage(event.target.value)} rows={6} aria-invalid={Boolean(errors.message)} aria-describedby={errors.message ? "message-error" : "message-help"} className={`${field} py-3 leading-6`} /><span id="message-help" className="mt-1.5 block text-xs text-white/35">Do not attach sensitive footage or payment details to the first message.</span></Field>

    {category === "compliance" && <p className="mt-5 flex gap-2 rounded-xl border border-amber-300/20 bg-amber-300/[.06] p-4 text-xs leading-5 text-amber-100/80"><CircleAlert size={15} className="mt-0.5 shrink-0" />Include the relevant project reference and the authorization concern. Avoid unrelated personal information.</p>}
    <button type="submit" disabled={phase === "opening"} className="mt-6 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 font-semibold text-white transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 disabled:cursor-wait disabled:opacity-65">
      {phase === "opening" ? <><LoaderCircle size={17} className="animate-spin motion-reduce:animate-none" />Opening email app…</> : <><Mail size={17} />Open email draft</>}
    </button>
    <div aria-live="polite" className="mt-4 min-h-6">
      {phase === "ready" && <p className="flex items-center gap-2 text-sm text-emerald-200"><Check size={16} />Email draft opened. Review it, then send it from your email app.</p>}
      {phase === "error" && <p className="flex items-center gap-2 text-sm text-rose-200"><CircleAlert size={16} />Your email app did not open. Write to <a className="underline" href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.</p>}
    </div>
  </form>;
}

function Field({ label, error, className = "", children }: { label: string; error?: string; className?: string; children: React.ReactNode }) {
  const id = `${label.toLowerCase()}-error`;
  return <label className={`block ${className}`}><span className="text-sm font-medium text-white/70">{label} <span aria-hidden="true" className="text-cyan-100">*</span></span>{children}{error && <span id={id} role="alert" className="mt-1.5 block text-xs text-rose-200">{error}</span>}</label>;
}
