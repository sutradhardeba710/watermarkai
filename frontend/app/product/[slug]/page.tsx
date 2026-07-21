import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, Check, Info, ShieldCheck } from "lucide-react";

import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import { productFeatureBySlug, productFeatures } from "@/components/productConfig";
import { ExamplesGallery } from "@/components/marketing/ExamplesGallery";
import { ProductHeroVisual } from "@/components/marketing/ProductVisuals";

type Props = { params: { slug: string } };

export function generateStaticParams() {
  return productFeatures.map((feature) => ({ slug: feature.slug }));
}

export function generateMetadata({ params }: Props): Metadata {
  const feature = productFeatureBySlug.get(params.slug);
  if (!feature) return {};
  return {
    title: `${feature.shortTitle} — ClearFrame`,
    description: feature.description,
    alternates: { canonical: feature.href },
    openGraph: {
      title: `${feature.shortTitle} — ClearFrame`,
      description: feature.description,
      url: feature.href,
      type: "website",
      images: [{ url: "/demo/owned-after.png", width: 1200, height: 630, alt: `${feature.shortTitle} in ClearFrame` }],
    },
    twitter: { card: "summary_large_image", title: `${feature.shortTitle} — ClearFrame`, description: feature.description, images: ["/demo/owned-after.png"] },
  };
}

export default function ProductFeaturePage({ params }: Props) {
  const feature = productFeatureBySlug.get(params.slug);
  if (!feature) notFound();
  const Icon = feature.icon;

  return <main className="min-h-screen overflow-hidden bg-[#07080f] text-[#f5f6fa]">
    <Navbar />
    <article>
      <header className="relative px-5 pb-24 pt-32 sm:px-8 sm:pt-40 lg:px-10">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[44rem] bg-[radial-gradient(ellipse_at_top,rgba(79,124,255,.2),transparent_65%)]" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-14 lg:grid-cols-[.82fr_1.18fr]">
          <div>
            <span className="grid h-12 w-12 place-items-center rounded-2xl border border-cyan-200/20 bg-gradient-to-br from-[#4f7cff]/25 to-[#6d5ef7]/25 text-cyan-100"><Icon size={22} /></span>
            <p className="mt-7 text-xs font-semibold uppercase tracking-[.18em] text-cyan-100">{feature.eyebrow}</p>
            <h1 className="mt-4 max-w-2xl text-5xl font-semibold leading-[.98] tracking-[-.055em] sm:text-6xl">{feature.title}.</h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-white/68">{feature.description}</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link href={feature.primaryCta.href} className="inline-flex min-h-12 items-center justify-center rounded-full bg-gradient-to-r from-[#4f7cff] via-[#6d5ef7] to-[#8b5cf6] px-6 font-semibold text-white shadow-[0_12px_32px_rgba(79,124,255,.26)] transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">{feature.primaryCta.label}</Link>
              <Link href={feature.secondaryCta.href} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-full border border-white/15 px-6 font-semibold text-white transition hover:bg-white/[.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">{feature.secondaryCta.label} <ArrowRight size={16} /></Link>
            </div>
            <div className="mt-7 flex flex-wrap gap-2">{feature.bullets.map((bullet) => <span key={bullet} className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[.025] px-3 py-2 text-xs text-white/55"><Check size={12} className="text-cyan-200" />{bullet}</span>)}</div>
          </div>
          <ProductHeroVisual kind={feature.slug as "ai-detection" | "manual-masking" | "temporal-tracking" | "review-export" | "examples"} />
        </div>
      </header>

      {feature.slug === "examples" && <ExamplesGallery />}

      <section className={`${feature.slug === "examples" ? "bg-[#07080f] text-white" : "bg-[#f5f6f8] text-[#0c0e1a]"} py-24 sm:py-32`}>
        <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
          <div className="grid gap-8 lg:grid-cols-[.75fr_1.25fr] lg:gap-16">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[.18em] ${feature.slug === "examples" ? "text-cyan-100" : "text-[#4f7cff]"}`}>Workflow</p>
              <h2 className="mt-4 text-4xl font-semibold tracking-[-.045em] sm:text-5xl">{feature.workflowTitle}</h2>
              <p className={`mt-5 max-w-lg leading-7 ${feature.slug === "examples" ? "text-white/55" : "text-slate-600"}`}>{feature.workflowIntro}</p>
            </div>
            <ol className={`relative grid gap-px overflow-hidden rounded-3xl border sm:grid-cols-2 ${feature.slug === "examples" ? "border-white/10 bg-white/10" : "border-slate-200 bg-slate-200"}`}>
              {feature.workflow.map((step, index) => <li key={step.title} className={`${feature.slug === "examples" ? "bg-[#10121f]" : "bg-white"} p-6 sm:p-7`}><span className={`text-xs font-bold tabular-nums ${feature.slug === "examples" ? "text-cyan-100" : "text-[#4f7cff]"}`}>{String(index + 1).padStart(2, "0")}</span><h3 className="mt-4 text-lg font-semibold">{step.title}</h3><p className={`mt-2 text-sm leading-6 ${feature.slug === "examples" ? "text-white/50" : "text-slate-600"}`}>{step.description}</p></li>)}
            </ol>
          </div>
        </div>
      </section>

      <section className={`${feature.slug === "examples" ? "bg-[#f5f6f8] text-[#0c0e1a]" : "bg-[#07080f] text-white"} py-24 sm:py-32`}>
        <div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10">
          <p className={`text-xs font-semibold uppercase tracking-[.18em] ${feature.slug === "examples" ? "text-[#4f7cff]" : "text-cyan-100"}`}>Capabilities in context</p>
          <h2 className="mt-4 max-w-3xl text-4xl font-semibold tracking-[-.045em] sm:text-5xl">{feature.capabilitiesTitle}</h2>
          <div className={`mt-12 grid gap-px overflow-hidden rounded-3xl border sm:grid-cols-2 ${feature.slug === "examples" ? "border-slate-200 bg-slate-200" : "border-white/10 bg-white/10"}`}>
            {feature.capabilities.map((item, index) => <article key={item.title} className={`${feature.slug === "examples" ? "bg-white" : "bg-[#10121f]"} p-7 sm:p-8`}><div className={`grid h-10 w-10 place-items-center rounded-xl ${feature.slug === "examples" ? "bg-[#4f7cff]/10 text-[#4f7cff]" : "bg-cyan-300/10 text-cyan-100"}`}><Icon size={18} /></div><p className={`mt-6 text-xs font-bold uppercase tracking-[.14em] ${feature.slug === "examples" ? "text-slate-400" : "text-white/30"}`}>Capability {String(index + 1).padStart(2, "0")}</p><h3 className="mt-2 text-xl font-semibold">{item.title}</h3><p className={`mt-3 leading-7 ${feature.slug === "examples" ? "text-slate-600" : "text-white/52"}`}>{item.description}</p></article>)}
          </div>
        </div>
      </section>

      {feature.examples.length > 0 && <section className="bg-[#f5f6f8] py-24 text-[#0c0e1a] sm:py-32"><div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10"><div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end"><div><p className="text-xs font-semibold uppercase tracking-[.18em] text-[#4f7cff]">Practical review states</p><h2 className="mt-4 max-w-2xl text-4xl font-semibold tracking-[-.045em] sm:text-5xl">Know what to look for next.</h2></div><p className="max-w-md leading-7 text-slate-600">Each state points to a concrete next action instead of leaving you with a vague score or success message.</p></div><div className="mt-12 grid gap-4 md:grid-cols-2">{feature.examples.map((item, index) => <article key={item.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_12px_32px_rgba(21,24,31,.05)]"><div className="flex items-start gap-4"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[#4f7cff]/10 text-sm font-bold text-[#4f7cff]">{index + 1}</span><div><h3 className="font-semibold">{item.title}</h3><p className="mt-2 text-sm leading-6 text-slate-600">{item.description}</p></div></div></article>)}</div></div></section>}

      <section className="bg-[#0c0e1a] py-24 sm:py-28"><div className="mx-auto max-w-7xl px-5 sm:px-8 lg:px-10"><div className="grid gap-8 rounded-[2rem] border border-amber-300/20 bg-[radial-gradient(circle_at_top_right,rgba(251,191,36,.09),transparent_45%)] p-8 sm:p-10 lg:grid-cols-[.72fr_1.28fr]"><div><div className="flex items-center gap-2 text-amber-200"><Info size={18} /><span className="text-xs font-semibold uppercase tracking-[.18em]">What to expect</span></div><h2 className="mt-5 text-3xl font-semibold tracking-[-.04em] sm:text-4xl">Keep the limitation visible before the job starts.</h2></div><ul className="grid gap-3 sm:grid-cols-2">{feature.limitations.map((limitation) => <li key={limitation} className="flex gap-3 rounded-2xl border border-white/10 bg-white/[.025] p-4 text-sm leading-6 text-white/60"><ShieldCheck size={17} className="mt-0.5 shrink-0 text-amber-200" />{limitation}</li>)}</ul></div></div></section>

      <section className="bg-[#07080f] px-5 py-20 sm:px-8 sm:py-24"><div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-8 rounded-[2rem] border border-cyan-300/20 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,.14),transparent_50%)] p-8 sm:flex-row sm:items-center sm:p-12"><div><p className="text-xs font-semibold uppercase tracking-[.18em] text-cyan-100">Next step</p><h2 className="mt-4 max-w-2xl text-3xl font-semibold tracking-[-.04em] sm:text-4xl">{feature.benefit}</h2><p className="mt-3 max-w-2xl leading-7 text-white/55">Start with authorized footage, review every selected region, and use a preview before full processing.</p></div><Link href={feature.primaryCta.href} className="inline-flex min-h-12 shrink-0 items-center justify-center rounded-full bg-white px-6 font-semibold text-[#07080f] transition hover:bg-cyan-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300">{feature.primaryCta.label}</Link></div></section>
    </article>
    <Footer />
  </main>;
}
