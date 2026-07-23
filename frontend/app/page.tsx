import type { Metadata } from "next";

import { MarketingHeader } from "@/components/marketing/MarketingHeader";
import { HeroSection } from "@/components/marketing/HeroSection";
import { VideoComparisonShowcase } from "@/components/marketing/VideoComparisonShowcase";
import { WorkflowSection } from "@/components/marketing/WorkflowSection";
import { BenefitsSection } from "@/components/marketing/BenefitsSection";
import { UseCasesSection } from "@/components/marketing/UseCasesSection";
import { QualityComparison } from "@/components/marketing/QualityComparison";
import { FeatureGrid } from "@/components/marketing/FeatureGrid";
import { PricingSection } from "@/components/marketing/PricingSection";
import { TrustAndComplianceSection } from "@/components/marketing/TrustAndComplianceSection";
import { FAQSection } from "@/components/marketing/FAQSection";
import { FinalCTA } from "@/components/marketing/FinalCTA";
import { MarketingFooter } from "@/components/marketing/MarketingFooter";
import { faqItems } from "@/components/marketing/content";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");

export const metadata: Metadata = {
  title: { absolute: "AI Video Watermark Remover Online | ClearFrame" },
  description:
    "Remove watermarks, logos, timestamps, and hardcoded subtitles from videos you own. Use AI detection, manual masking, a free preview, and high-quality export.",
  keywords: [
    "AI video watermark remover",
    "video watermark remover online",
    "remove watermark from video",
    "remove logo from video",
    "remove timestamp from video",
    "remove hardcoded subtitles from video",
    "video overlay remover",
    "MP4 watermark remover",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    title: "AI Video Watermark Remover Online | ClearFrame",
    description:
      "Remove watermarks, logos, timestamps, and hardcoded subtitles from videos you own with AI detection, manual mask control, and preview-first processing.",
    url: "/",
    siteName: "ClearFrame",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "ClearFrame AI video watermark remover with preview and manual control" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Video Watermark Remover Online | ClearFrame",
    description: "Remove owned watermarks, logos, timestamps, and hardcoded subtitles with reviewable AI video cleanup.",
    images: ["/og.png"],
  },
};

const structuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      name: "ClearFrame",
      url: siteUrl,
      description: "An online AI video watermark remover with manual mask control for authorized footage.",
    },
    {
      "@type": "WebApplication",
      name: "ClearFrame",
      url: siteUrl,
      applicationCategory: "MultimediaApplication",
      operatingSystem: "Any",
      browserRequirements: "Requires a modern web browser with JavaScript enabled.",
      description:
        "Remove watermarks, logos, timestamps, hardcoded subtitles, and visual overlays from videos you own or are authorized to edit.",
      featureList: [
        "AI-assisted watermark and overlay detection",
        "Manual rectangle, polygon, brush, and eraser masking",
        "Static and moving-region tracking",
        "Free short preview before full processing",
        "Before-and-after comparison",
        "Audio-preserving MP4 export",
      ],
    },
    {
      "@type": "FAQPage",
      mainEntity: faqItems.map((item) => ({
        "@type": "Question",
        name: item.q,
        acceptedAnswer: { "@type": "Answer", text: item.a },
      })),
    },
  ],
};

export default function HomePage() {
  return (
    <main id="top" className="min-h-screen overflow-hidden bg-[#07080f] text-[#f5f6fa]">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData).replace(/</g, "\\u003c") }}
      />
      <MarketingHeader />
      <HeroSection />
      <VideoComparisonShowcase />
      <WorkflowSection />
      <BenefitsSection />
      <UseCasesSection />
      <QualityComparison />
      <FeatureGrid />
      <PricingSection />
      <TrustAndComplianceSection />
      <FAQSection />
      <FinalCTA />
      <MarketingFooter />
    </main>
  );
}
