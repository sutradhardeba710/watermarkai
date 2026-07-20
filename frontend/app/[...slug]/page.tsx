import type { Metadata } from "next";
import Link from "next/link";
import { Check, ChevronRight } from "lucide-react";
import { notFound } from "next/navigation";
import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { seoPageByPath, seoPages } from "@/components/seoPages";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");

type Props = { params: { slug: string[] } };

export const dynamicParams = false;
export function generateStaticParams() { return seoPages.map((page) => ({ slug: page.slug })); }

export function generateMetadata({ params }: Props): Metadata {
  const page = seoPageByPath.get(params.slug.join("/"));
  if (!page) return {};
  const path = `/${page.slug.join("/")}`;
  return {
    title: `${page.title} | ClearFrame`,
    description: page.description,
    alternates: { canonical: path },
    openGraph: { title: page.title, description: page.description, url: path, siteName: "ClearFrame", type: "website" },
    twitter: { card: "summary_large_image", title: page.title, description: page.description },
  };
}

export default function SeoMarketingPage({ params }: Props) {
  const page = seoPageByPath.get(params.slug.join("/"));
  if (!page) notFound();
  const path = `/${page.slug.join("/")}`;
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: page.title,
    description: page.description,
    url: `${siteUrl}${path}`,
    isPartOf: { "@type": "WebSite", name: "ClearFrame", url: siteUrl },
  };

  return <main className="min-h-screen bg-[#07080f] text-[#f5f6fa]">
    <Navbar />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }} />
    <article>
      <header className="relative overflow-hidden px-5 pb-24 pt-32 sm:px-8 sm:pt-40 lg:px-10">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[38rem] bg-[radial-gradient(ellipse_at_top,rgba(79,124,255,.22),transparent_65%)]" />
        <div className="relative mx-auto max-w-5xl">
          <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm text-white/45"><Link href="/" className="hover:text-white">Home</Link><ChevronRight size={14} /><span>{page.title}</span></nav>
          <p className="mt-12 text-xs font-semibold uppercase tracking-[.18em] text-cyan-200">{page.eyebrow}</p>
          <h1 className="mt-5 max-w-4xl text-5xl font-semibold leading-[.98] tracking-[-.05em] sm:text-6xl lg:text-7xl">{page.heading}</h1>
          <p className="mt-7 max-w-3xl text-lg leading-8 text-white/65 sm:text-xl">{page.intro}</p>
        </div>
      </header>
      <section className="bg-[#f6f7fa] py-20 text-[#0c0e1a] sm:py-28">
        <div className="mx-auto grid max-w-5xl gap-5 px-5 sm:px-8 lg:grid-cols-2">
          {page.sections.map((section) => <section key={section.title} className="rounded-3xl border border-slate-200 bg-white p-7 shadow-[0_12px_35px_rgba(21,24,31,.06)] sm:p-8">
            <h2 className="text-2xl font-semibold tracking-[-.03em]">{section.title}</h2>
            <p className="mt-4 leading-7 text-slate-600">{section.body}</p>
            {section.bullets && <ul className="mt-5 space-y-3 text-sm text-slate-700">{section.bullets.map((bullet) => <li key={bullet} className="flex gap-2"><Check size={16} className="mt-0.5 shrink-0 text-[#4f7cff]" />{bullet}</li>)}</ul>}
          </section>)}
        </div>
      </section>
      <section className="px-5 py-20 sm:px-8 sm:py-24"><div className="mx-auto flex max-w-5xl flex-col items-start justify-between gap-8 rounded-3xl border border-white/10 bg-[#10121f] p-8 sm:flex-row sm:items-center sm:p-10"><div><h2 className="text-3xl font-semibold tracking-[-.04em]">Start an authorized video project.</h2><p className="mt-3 text-white/55">Create an account, upload footage you can legally edit, and review the result before export.</p></div><Link href="/signup" className="shrink-0 rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-6 py-3.5 font-semibold text-white">Create an account</Link></div></section>
    </article>
    <Footer />
  </main>;
}