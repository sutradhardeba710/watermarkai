import type { Metadata } from "next";
import { notFound } from "next/navigation";

import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { seoPageByPath, seoPages } from "@/components/seoPages";
import { SeoPageView } from "@/components/marketing/SeoPageView";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");
type Props = { params: { slug: string[] } };

export const dynamicParams = false;
export function generateStaticParams() { return seoPages.map((page) => ({ slug: page.slug })); }

export function generateMetadata({ params }: Props): Metadata {
  const page = seoPageByPath.get(params.slug.join("/"));
  if (!page) return {};
  const path = `/${page.slug.join("/")}`;
  return {
    title: page.title,
    description: page.description,
    alternates: { canonical: path },
    openGraph: { title: page.title, description: page.description, url: path, siteName: "ClearFrame", type: "website", images: [{ url: "/demo/owned-after.png", width: 1200, height: 630, alt: `${page.title} — ClearFrame` }] },
    twitter: { card: "summary_large_image", title: page.title, description: page.description, images: ["/demo/owned-after.png"] },
  };
}

export default function SeoMarketingPage({ params }: Props) {
  const page = seoPageByPath.get(params.slug.join("/"));
  if (!page) notFound();
  const path = `/${page.slug.join("/")}`;
  const webPage = { "@context": "https://schema.org", "@type": "WebPage", name: page.title, description: page.description, url: `${siteUrl}${path}`, isPartOf: { "@type": "WebSite", name: "ClearFrame", url: siteUrl } };
  const faq = page.kind === "faq" ? { "@context": "https://schema.org", "@type": "FAQPage", mainEntity: page.sections.flatMap((section) => section.entries ?? []).map((entry) => ({ "@type": "Question", name: entry.title, acceptedAnswer: { "@type": "Answer", text: entry.body } })) } : null;

  return <main className="min-h-screen overflow-hidden bg-[#07080f] text-[#f5f6fa]"><Navbar /><script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faq ? { "@context": "https://schema.org", "@graph": [webPage, faq] } : webPage).replace(/</g, "\\u003c") }} /><SeoPageView page={page} /><Footer /></main>;
}
