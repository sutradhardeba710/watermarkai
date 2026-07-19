"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Check, Sparkles } from "lucide-react";
import { footerColumns, footerSocials, footerTrustBadges, type FooterLink } from "./footerConfig";
import { scrollToSection } from "@/utils/scrollToSection";

function FooterLinkItem({ link }: { link: FooterLink }) {
  const className = "group inline-flex items-center gap-2 text-sm text-white/65 transition duration-150 hover:text-white hover:underline hover:underline-offset-4";
  if (link.href.startsWith("#")) return <Link href={`/${link.href}`} onClick={(event) => { if (window.location.pathname === "/") { event.preventDefault(); scrollToSection(link.href); } }} className={className}>{link.label}</Link>;
  if (link.href.startsWith("mailto:")) return <a href={link.href} className={className}>{link.label}</a>;
  return <Link href={link.href} className={className}>{link.label}</Link>;
}

function FooterColumn({ title, links }: { title: string; links: FooterLink[] }) {
  return <nav aria-label={`${title} links`}><h3 className="text-xs font-semibold uppercase tracking-[.18em] text-white/45">{title}</h3><ul className="mt-5 space-y-3.5">{links.map((link) => <li key={link.label}><FooterLinkItem link={link} /></li>)}</ul></nav>;
}

export default function Footer() {
  const [year, setYear] = useState<number | null>(null);
  useEffect(() => setYear(new Date().getFullYear()), []);
  return <footer id="resources" className="scroll-mt-24 border-t border-white/10 bg-[#0a0b0f]">
    <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">

      <div className="grid gap-12 py-16 sm:grid-cols-2 lg:grid-cols-[1.45fr_repeat(4,1fr)]"><div className="sm:col-span-2 lg:col-span-1"><Link href="/" className="flex items-center gap-2.5 text-lg font-semibold text-white"><span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] to-[#6d5ef7]"><Sparkles size={18} /></span>ClearFrame</Link><p className="mt-4 max-w-xs text-sm leading-6 text-white/55">AI-assisted video cleanup for footage you own or are licensed to edit.</p><div className="mt-4 flex items-center gap-2">{footerSocials.map(({ label, href, icon: Icon }) => <a key={label} href={href} target="_blank" rel="noreferrer" aria-label={label} className="grid h-9 w-9 place-items-center rounded-full border border-white/10 text-white/55 transition hover:border-white/25 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300"><Icon size={16} /></a>)}</div></div>{footerColumns.map((column) => <FooterColumn key={column.title} {...column} />)}</div>
      <div className="flex flex-wrap gap-2 border-t border-white/[.07] py-5">{footerTrustBadges.map((badge) => <span key={badge} className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[.03] px-3 py-1.5 text-xs text-white/60"><Check size={13} className="text-cyan-200" />{badge}</span>)}</div>
      <div className="flex flex-col gap-3 border-t border-white/[.07] py-5 text-xs text-white/45 sm:flex-row sm:items-center sm:justify-between"><p>© {year ?? ""} ClearFrame. All rights reserved.</p><div className="flex flex-wrap items-center gap-4"><a href="#resources" onClick={(event) => { event.preventDefault(); scrollToSection("resources"); }} className="hover:text-white">Terms</a><a href="#resources" onClick={(event) => { event.preventDefault(); scrollToSection("resources"); }} className="hover:text-white">Privacy</a><a href="#resources" onClick={(event) => { event.preventDefault(); scrollToSection("resources"); }} className="hover:text-white">Cookies</a><Link href="/status" className="inline-flex items-center gap-1.5 hover:text-white"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />All systems operational</Link></div></div>
    </div>
  </footer>;
}
