import type { Metadata } from "next";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Pricing from "@/components/Pricing";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Compare ClearFrame plans, upload limits, processing capacity, retention, and support. Quick previews are free and full processing uses 100 credits per job.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "ClearFrame pricing",
    description:
      "Transparent plans for authorized video cleanup, from free previews to higher-capacity production workflows.",
    url: "/pricing",
    images: [{ url: "/demo/owned-after.png", width: 1200, height: 630, alt: "ClearFrame video cleanup preview" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "ClearFrame pricing",
    description: "Compare ClearFrame plans and processing capacity.",
    images: ["/demo/owned-after.png"],
  },
};

export default function PricingPage() {
  return (
    <main className="min-h-screen bg-[#080910] text-white">
      <Navbar />
      <h1 className="sr-only">ClearFrame pricing plans</h1>
      <div className="pt-16">
        <Pricing />
      </div>
      <Footer />
    </main>
  );
}
