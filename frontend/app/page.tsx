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
  title: { absolute: "AI Watermark Remover Free Online | Video, Photo & Image Cleanup — ClearFrame" },
  description:
    "Free AI watermark remover for videos, photos, and images. Remove logos, timestamps, hardcoded subtitles, and unwanted overlays with frame-accurate AI inpainting, free batch queue, and preview-first processing.",
  keywords: [
    "ai watermark remover",
    "free ai watermark batch remover",
    "free ai batch watermark remover",
    "ai video watermark remover free",
    "ai image watermark remover free",
    "ai watermark image remover",
    "free sora ai watermark remover",
    "remove watermark from video ai free",
    "can ai remove watermarks from photos",
    "remove watermark from photo ai",
    "video watermark remover online",
    "free ai remove watermark from image",
    "MP4 watermark remover",
    "remove logo from video",
    "remove hardcoded subtitles from video",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    title: "AI Watermark Remover Free Online | Video, Photo & Image Cleanup — ClearFrame",
    description:
      "Remove watermarks, logos, timestamps, and hardcoded subtitles from videos and photos with AI detection, manual mask control, and preview-first processing.",
    url: "/",
    siteName: "ClearFrame",
    type: "website",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "ClearFrame AI watermark remover with preview and manual control" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Watermark Remover Free Online | Video, Photo & Image Cleanup — ClearFrame",
    description: "Remove watermarks, logos, timestamps, and overlays from videos and photos with reviewable AI cleanup.",
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
      description: "An online AI watermark remover with manual mask control, batch tools, and instant preview for authorized media.",
    },
    {
      "@type": "WebApplication",
      name: "ClearFrame AI Watermark Remover",
      url: siteUrl,
      applicationCategory: "MultimediaApplication",
      operatingSystem: "Any",
      browserRequirements: "Requires a modern web browser with JavaScript enabled.",
      description:
        "Remove watermarks, logos, timestamps, hardcoded subtitles, and visual overlays from videos, images, and photos you own or are authorized to edit.",
      featureList: [
        "AI-assisted watermark and overlay detection for videos and photos",
        "Free AI watermark batch remover workflow",
        "Sora AI and synthetic video watermark cleanup",
        "Manual rectangle, polygon, brush, and eraser masking",
        "Static and moving-region temporal tracking",
        "Free short preview before full processing",
        "Before-and-after comparison slider",
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
