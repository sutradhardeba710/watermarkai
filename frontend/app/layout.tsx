import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: { default: "ClearFrame | Authorized Video Cleanup", template: "%s | ClearFrame" },
  description: "AI-assisted detection, frame-accurate masking, preview approval, and controlled export for footage you own or are licensed to edit.",
  applicationName: "ClearFrame",
  keywords: ["authorized video cleanup", "video overlay cleanup", "video masking", "watermark detection", "video inpainting", "frame accurate masking"],
  authors: [{ name: "ClearFrame" }],
  creator: "ClearFrame",
  publisher: "ClearFrame",
  robots: { index: true, follow: true, googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1, "max-video-preview": -1 } },
  openGraph: { title: "ClearFrame | Authorized Video Cleanup", description: "Reviewable, frame-accurate cleanup for footage you own or are licensed to edit.", type: "website", siteName: "ClearFrame", url: "/" },
  twitter: { card: "summary_large_image", title: "ClearFrame | Authorized Video Cleanup", description: "AI-assisted cleanup for authorized edits." },
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><Providers>{children}</Providers></body></html>;
}