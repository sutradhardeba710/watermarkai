"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Check, LifeBuoy, Mail, MessageSquare, ShieldAlert } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

// Where each request type is routed. Kept here (not hard-coded inline) so the
// address is easy to change in one place. Uses a mailto: submission because no
// backend contact endpoint or transactional email service is configured yet —
// this reaches a real inbox instead of posting into a void.
const SUPPORT_EMAIL = "support@clearframe.app";

const TOPICS = [
  { value: "support", label: "Product support", desc: "Account or project help", icon: LifeBuoy },
  { value: "security", label: "Security report", desc: "Report a vulnerability", icon: ShieldAlert },
  { value: "business", label: "Business inquiry", desc: "Agency or team needs", icon: MessageSquare },
] as const;

type Topic = (typeof TOPICS)[number]["value"];

export default function ContactPage() {
  const [topic, setTopic] = useState<Topic>("support");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [touched, setTouched] = useState(false);

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const errors = {
    name: name.trim().length === 0,
    email: !emailValid,
    message: message.trim().length < 10,
  };
  const hasErrors = errors.name || errors.email || errors.message;

  const topicLabel = TOPICS.find((t) => t.value === topic)!.label;

  // Prebuild the mailto link so the button is a real anchor (works even with JS
  // disabled) and the browser handles opening the user's mail client.
  const mailtoHref = useMemo(() => {
    const subject = `[${topicLabel}] Message from ${name.trim() || "ClearFrame user"}`;
    const body = [
      `Topic: ${topicLabel}`,
      `Name: ${name.trim()}`,
      `Email: ${email.trim()}`,
      "",
      message.trim(),
    ].join("\n");
    return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  }, [topicLabel, name, email, message]);

  function handleSubmit(e: React.MouseEvent<HTMLAnchorElement>) {
    if (hasErrors) {
      e.preventDefault();
      setTouched(true);
    }
  }

  const inputBase =
    "w-full rounded-xl border bg-white/[.03] px-4 py-3 text-sm text-white outline-none transition placeholder:text-white/30 focus:border-[#4f7cff]/50 focus:shadow-[0_0_0_3px_rgba(79,124,255,.12)]";
  const okBorder = "border-white/10";
  const errBorder = "border-rose-400/40";

  return (
    <main className="min-h-screen bg-[#07080f] text-[#f5f6fa]">
      <Navbar />

      <div className="relative overflow-hidden px-5 pb-20 pt-32 sm:px-8 sm:pt-36 lg:px-10">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[32rem] bg-[radial-gradient(ellipse_at_top,rgba(79,124,255,.18),transparent_65%)]" />

        <div className="relative mx-auto max-w-2xl">
          <div className="text-center">
            <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-[#4f7cff]/20 to-[#6d5ef7]/20 text-[#9eb4ff]">
              <Mail className="h-7 w-7" />
            </span>
            <h1 className="mt-5 text-4xl font-semibold tracking-tight sm:text-5xl">Talk with the team</h1>
            <p className="mx-auto mt-4 max-w-md text-base leading-7 text-white/60">
              Pick what your message is about, and we&apos;ll get it to the right place.
            </p>
          </div>

          <form className="mt-10 rounded-3xl border border-white/[.08] bg-white/[.02] p-6 sm:p-8">
            {/* Topic selector */}
            <fieldset>
              <legend className="text-sm font-medium text-white/70">What&apos;s this about?</legend>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                {TOPICS.map(({ value, label, desc, icon: Icon }) => {
                  const selected = topic === value;
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setTopic(value)}
                      aria-pressed={selected}
                      className={`flex flex-col items-start gap-2 rounded-2xl border p-4 text-left transition ${
                        selected
                          ? "border-[#4f7cff]/50 bg-[#4f7cff]/10 shadow-[0_0_0_1px_rgba(79,124,255,.25)]"
                          : "border-white/10 bg-white/[.02] hover:border-white/20"
                      }`}
                    >
                      <span className={`grid h-9 w-9 place-items-center rounded-xl ${selected ? "bg-[#4f7cff]/20 text-[#b7c7ff]" : "bg-white/[.06] text-white/55"}`}>
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="text-sm font-semibold text-white">{label}</span>
                      <span className="text-xs text-white/45">{desc}</span>
                    </button>
                  );
                })}
              </div>
            </fieldset>

            {/* Name + email */}
            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              <label className="block">
                <span className="text-sm font-medium text-white/70">Your name</span>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jordan Rivera"
                  className={`mt-2 ${inputBase} ${touched && errors.name ? errBorder : okBorder}`}
                />
                {touched && errors.name && <span className="mt-1.5 block text-xs text-rose-300">Please enter your name.</span>}
              </label>
              <label className="block">
                <span className="text-sm font-medium text-white/70">Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className={`mt-2 ${inputBase} ${touched && errors.email ? errBorder : okBorder}`}
                />
                {touched && errors.email && <span className="mt-1.5 block text-xs text-rose-300">Enter a valid email so we can reply.</span>}
              </label>
            </div>

            {/* Message */}
            <label className="mt-5 block">
              <span className="text-sm font-medium text-white/70">Message</span>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={5}
                placeholder={
                  topic === "security"
                    ? "Describe the issue. Please don't include sensitive footage in this first message."
                    : "Tell us what you need help with…"
                }
                className={`mt-2 resize-y ${inputBase} ${touched && errors.message ? errBorder : okBorder}`}
              />
              {touched && errors.message && <span className="mt-1.5 block text-xs text-rose-300">Please add a bit more detail (at least 10 characters).</span>}
            </label>

            {topic === "security" && (
              <p className="mt-4 flex items-start gap-2 rounded-xl border border-amber-400/20 bg-amber-400/[.06] px-4 py-3 text-xs leading-5 text-amber-100/80">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
                For responsible disclosure, avoid attaching sensitive footage or exploit details until we reply with a secure channel.
              </p>
            )}

            <a
              href={mailtoHref}
              onClick={handleSubmit}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-5 py-3.5 text-sm font-semibold text-white transition hover:brightness-110"
            >
              <Mail className="h-4 w-4" />
              Send message
            </a>

            <p className="mt-4 flex items-center justify-center gap-2 text-center text-xs text-white/40">
              <Check className="h-3.5 w-3.5 text-cyan-200" />
              Opens your email app addressed to{" "}
              <a href={`mailto:${SUPPORT_EMAIL}`} className="text-white/60 underline underline-offset-2 hover:text-white">
                {SUPPORT_EMAIL}
              </a>
            </p>
          </form>

          <p className="mt-6 text-center text-sm text-white/45">
            Looking for quick answers first?{" "}
            <Link href="/support" className="text-[#b7c7ff] underline underline-offset-2 hover:text-white">
              Visit the Help Center
            </Link>
          </p>
        </div>
      </div>

      <Footer />
    </main>
  );
}
