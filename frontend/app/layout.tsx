import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import { Providers } from "@/components/Providers";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "ClearFrame | AI Watermark Remover — Free Video, Image & Photo Cleanup",
    template: "%s | ClearFrame AI Watermark Remover",
  },
  description:
    "Free online AI watermark remover for videos, photos, and images. Remove logos, timestamps, hardcoded subtitles, and unwanted overlays with frame-accurate AI inpainting.",
  applicationName: "ClearFrame",
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
  ],
  authors: [{ name: "ClearFrame" }],
  creator: "ClearFrame",
  publisher: "ClearFrame",
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1, "max-video-preview": -1 },
  },
  openGraph: {
    title: "ClearFrame | AI Watermark Remover — Free Video, Image & Photo Cleanup",
    description: "Free online AI watermark remover with frame-accurate masking, instant preview, and high-quality export.",
    type: "website",
    siteName: "ClearFrame",
    url: "/",
  },
  twitter: {
    card: "summary_large_image",
    title: "ClearFrame | AI Watermark Remover — Free Video, Image & Photo Cleanup",
    description: "Free online AI watermark remover for video, images, and photos with frame-level control.",
  },
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=AW-18350343160"
          strategy="afterInteractive"
        />
        <Script id="google-ads-tag" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'AW-18350343160');
          `}
        </Script>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}