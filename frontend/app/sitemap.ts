import type { MetadataRoute } from "next";
import { productFeatures } from "@/components/productConfig";
import { seoPages } from "@/components/seoPages";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const staticPaths = ["", "/product", "/pricing", "/contact", "/support"];
  return [
    ...staticPaths.map((path, index) => ({ url: `${siteUrl}${path}`, lastModified: now, changeFrequency: index === 0 ? "weekly" as const : "monthly" as const, priority: index === 0 ? 1 : 0.8 })),
    ...productFeatures.map((feature) => ({ url: `${siteUrl}${feature.href}`, lastModified: now, changeFrequency: "monthly" as const, priority: 0.75 })),
    ...seoPages.map((page) => ({ url: `${siteUrl}/${page.slug.join("/")}`, lastModified: now, changeFrequency: "monthly" as const, priority: 0.65 })),
  ];
}
