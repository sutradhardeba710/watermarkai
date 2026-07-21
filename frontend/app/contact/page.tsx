import type { Metadata } from "next";
import { Mail, MessageSquareText, ShieldCheck } from "lucide-react";

import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { ContactForm } from "@/components/marketing/ContactForm";

export const metadata: Metadata = {
  title: "Contact ClearFrame",
  description: "Contact ClearFrame for general support, billing help, technical issues, agency inquiries, or compliance reports.",
  alternates: { canonical: "/contact" },
  openGraph: { title: "Contact ClearFrame", description: "Get product, billing, technical, business, or compliance help.", url: "/contact", type: "website" },
};

export default function ContactPage() {
  return <main className="min-h-screen bg-[#07080f] text-[#f5f6fa]"><Navbar /><header className="relative overflow-hidden px-5 pb-16 pt-32 sm:px-8 sm:pt-40 lg:px-10"><div className="pointer-events-none absolute inset-x-0 top-0 h-[36rem] bg-[radial-gradient(ellipse_at_top,rgba(79,124,255,.2),transparent_65%)]" /><div className="relative mx-auto max-w-4xl text-center"><span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-cyan-300/20 bg-[#4f7cff]/15 text-cyan-100"><MessageSquareText /></span><p className="mt-7 text-xs font-semibold uppercase tracking-[.18em] text-cyan-100">Contact ClearFrame</p><h1 className="mt-4 text-5xl font-semibold tracking-[-.055em] sm:text-6xl">Start with the right context.</h1><p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-white/60">Choose a category, include a project or job reference when you have one, and we will have the information needed to understand the request.</p></div></header><section className="px-5 pb-24 sm:px-8 sm:pb-32 lg:px-10"><div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[.7fr_1.3fr]"><aside className="space-y-4"><div className="rounded-3xl border border-white/10 bg-white/[.025] p-6"><Mail className="text-cyan-100" /><h2 className="mt-5 text-xl font-semibold">One real contact path</h2><p className="mt-3 text-sm leading-6 text-white/50">The form opens a complete draft addressed to <a href="mailto:support@clearframe.app" className="text-cyan-100 underline underline-offset-4">support@clearframe.app</a>. It does not pretend a message was sent before you approve it in your email app.</p></div><div className="rounded-3xl border border-amber-300/20 bg-amber-300/[.045] p-6"><ShieldCheck className="text-amber-100" /><h2 className="mt-5 text-xl font-semibold">Keep sensitive media out of the first message</h2><p className="mt-3 text-sm leading-6 text-white/50">For security or compliance reports, send the project reference and a concise description. A secure follow-up path can be arranged if media is required.</p></div></aside><ContactForm /></div></section><Footer /></main>;
}
