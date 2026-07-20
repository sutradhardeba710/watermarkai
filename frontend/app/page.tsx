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
  title: "ClearFrame — AI Video Cleanup with Manual Mask Control",
  description:
    "Detect and remove unwanted logos, timestamps, subtitles, and overlays from videos you own or are authorized to edit. Review masks, preview results, and export cleaned footage.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "ClearFrame — AI Video Cleanup with Manual Mask Control",
    description:
      "Detect and remove unwanted overlays from footage you own or are licensed to edit. Review the mask, preview the result, and export cleaned video.",
    url: "/",
    siteName: "ClearFrame",
    type: "website",
    images: [{ url: "/demo/owned-after.png", width: 1200, height: 630, alt: "ClearFrame video cleanup preview" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "ClearFrame — AI Video Cleanup with Manual Mask Control",
    description: "Remove unwanted overlays from footage you own or are authorized to edit.",
    images: ["/demo/owned-after.png"],
  },
};

const structuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      name: "ClearFrame",
      url: siteUrl,
      description: "AI video cleanup with manual mask control for authorized footage.",
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
