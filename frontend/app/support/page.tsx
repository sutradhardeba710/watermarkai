import type { Metadata } from "next";
import Link from "next/link";
import { BadgeDollarSign, FileVideo2, LifeBuoy, Mail, ShieldCheck, Workflow } from "lucide-react";

import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { seoPageByPath } from "@/components/seoPages";

export const metadata: Metadata = {
  title: "ClearFrame Help Center",
  description: "Find ClearFrame help for projects, masks, previews, billing, supported formats, authorized use, and technical issues.",
  alternates: { canonical: "/support" },
  openGraph: { title: "ClearFrame Help Center", description: "Project, billing, format, policy, and contact help.", url: "/support", type: "website" },
};

const links = [
  { title: "Project workflow", body: "Upload, detection, masking, preview, processing, and export.", href: "/how-it-works", icon: Workflow },
  { title: "Billing and credits", body: "Plans, free previews, full-job costs, refunds, and cancellation.", href: "/pricing", icon: BadgeDollarSign },
  { title: "Supported formats", body: "MP4, MOV, WebM, codecs, media limits, and upload errors.", href: "/supported-formats", icon: FileVideo2 },
  { title: "Authorized use", body: "Allowed projects, prohibited ownership-mark removal, and reports.", href: "/authorized-use", icon: ShieldCheck },
];

export default function SupportPage() {
  const faq = seoPageByPath.get("faq")?.sections.flatMap((section) => section.entries ?? []).slice(0, 6) ?? [];
  return <main className="min-h-screen bg-[#07080f] text-[#f5f6fa]"><Navbar /><header className="relative overflow-hidden px-5 pb-20 pt-32 text-center sm:px-8 sm:pt-40"><div className="pointer-events-none absolute inset-x-0 top-0 h-[36rem] bg-[radial-gradient(ellipse_at_top,rgba(79,124,255,.2),transparent_65%)]" /><div className="relative mx-auto max-w-3xl"><span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-cyan-300/20 bg-[#4f7cff]/15 text-cyan-100"><LifeBuoy /></span><p className="mt-7 text-xs font-semibold uppercase tracking-[.18em] text-cyan-100">Help Center</p><h1 className="mt-4 text-4xl font-semibold sm:text-5xl tracking-[-.055em] sm:text-6xl">Find the next useful answer.</h1><p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-white/60">Start with the affected part of the workflow. If the documentation does not resolve it, contact support with the project or job reference.</p></div></header><section className="bg-[#f5f6f8] py-16 text-[#0c0e1a] sm:py-28"><div className="mx-auto max-w-6xl px-5 sm:px-8"><div className="grid gap-4 sm:grid-cols-2">{links.map(({ title, body, href, icon: Icon }) => <Link key={href} href={href} className="group rounded-3xl border border-slate-200 bg-white p-7 shadow-[0_12px_32px_rgba(21,24,31,.05)] transition hover:-translate-y-1 hover:border-[#4f7cff]/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4f7cff]"><span className="grid h-11 w-11 place-items-center rounded-xl bg-[#4f7cff]/10 text-[#4f7cff]"><Icon size={19} /></span><h2 className="mt-6 text-xl font-semibold">{title}</h2><p className="mt-2 leading-7 text-slate-600">{body}</p></Link>)}</div><div className="mx-auto mt-16 max-w-3xl"><h2 className="text-3xl font-semibold tracking-[-.04em]">Common questions</h2><div className="mt-7 space-y-3">{faq.map((item) => <details key={item.title} className="group rounded-2xl border border-slate-200 bg-white"><summary className="flex min-h-16 cursor-pointer list-none items-center justify-between gap-4 px-5 font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#4f7cff]"><span>{item.title}</span><span className="text-[#4f7cff] transition group-open:rotate-45">+</span></summary><p className="px-5 pb-6 leading-7 text-slate-600">{item.body}</p></details>)}</div><Link href="/faq" className="mt-6 inline-flex items-center gap-2 font-semibold text-[#4f7cff]">Read every FAQ <span aria-hidden="true">→</span></Link></div></div></section><section className="px-5 py-20 sm:px-8 sm:py-24"><div className="mx-auto flex max-w-5xl flex-col items-start justify-between gap-7 rounded-[2rem] border border-cyan-300/20 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,.14),transparent_50%)] p-8 sm:flex-row sm:items-center sm:p-10"><div><h2 className="text-3xl font-semibold tracking-[-.04em]">Still need help?</h2><p className="mt-3 max-w-2xl text-white/55">Choose General support, Billing help, Technical issue, Agency inquiry, or Compliance report.</p></div><Link href="/contact" className="inline-flex min-h-12 items-center gap-2 rounded-full bg-white px-6 font-semibold text-[#07080f]"><Mail size={16} />Contact us</Link></div></section><Footer /></main>;
}
