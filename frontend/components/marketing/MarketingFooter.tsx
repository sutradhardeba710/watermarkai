"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Check, Sparkles } from "lucide-react";

import { footerColumns, footerTrustBadges, type FooterLink } from "@/components/footerConfig";

function FooterLinkItem({ link }: { link: FooterLink }) {
  const className = "text-sm text-white/60 transition duration-150 hover:text-white hover:underline hover:underline-offset-4";
  if (link.href.startsWith("mailto:")) return <a href={link.href} className={className}>{link.label}</a>;
  return <Link href={link.href} className={className}>{link.label}</Link>;
}

function FooterColumn({ title, links }: { title: string; links: FooterLink[] }) {
  return (
    <nav aria-label={`${title} links`}>
      <h3 className="text-xs font-semibold uppercase tracking-[.18em] text-white/45">{title}</h3>
      <ul className="mt-5 space-y-3.5">
        {links.map((link) => (
          <li key={link.label}>
            <FooterLinkItem link={link} />
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function MarketingFooter() {
  const [year, setYear] = useState<number | null>(null);
  useEffect(() => setYear(new Date().getFullYear()), []);

  return (
    <footer id="resources" className="scroll-mt-24 border-t border-white/10 bg-[#07080f]">
      <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
        <div className="grid gap-12 py-16 sm:grid-cols-2 lg:grid-cols-[1.5fr_repeat(4,1fr)]">
          <div className="sm:col-span-2 lg:col-span-1">
            <Link href="/" className="flex items-center gap-2.5 text-lg font-semibold text-white">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6]">
                <Sparkles size={18} />
              </span>
              ClearFrame
            </Link>
            <p className="mt-4 max-w-xs text-sm leading-6 text-white/55">
              AI-assisted video cleanup for footage you own or are licensed to edit.
            </p>
          </div>
          {footerColumns.map((column) => (
            <FooterColumn key={column.title} {...column} />
          ))}
        </div>

        <div className="flex flex-wrap gap-2 border-t border-white/[.07] py-5">
          {footerTrustBadges.map((badge) => (
            <span key={badge} className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[.03] px-3 py-1.5 text-xs text-white/60">
              <Check size={13} className="text-cyan-200" />
              {badge}
            </span>
          ))}
        </div>

        <div className="flex flex-col gap-3 border-t border-white/[.07] py-5 text-xs text-white/45 sm:flex-row sm:items-center sm:justify-between">
          <p>© {year ?? ""} ClearFrame. All rights reserved.</p>
          <div className="flex flex-wrap items-center gap-4">
            <Link href="/terms" className="hover:text-white">Terms</Link>
            <Link href="/privacy" className="hover:text-white">Privacy</Link>
            <Link href="/acceptable-use" className="hover:text-white">Acceptable Use</Link>
            <Link href="/status" className="inline-flex items-center gap-1.5 hover:text-white">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> System status
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
