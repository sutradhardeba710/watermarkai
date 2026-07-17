import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/Providers";

export const metadata: Metadata = {
  title: "ClearFrame - Authorized Video Cleanup",
  description: "AI-assisted video cleanup for footage you own or are licensed to edit.",
  metadataBase: new URL("http://localhost:3000"),
  openGraph: { title: "ClearFrame - Authorized Video Cleanup", description: "Reviewable, frame-accurate cleanup for footage you own or are licensed to edit.", type: "website" },
  twitter: { card: "summary_large_image", title: "ClearFrame - Authorized Video Cleanup", description: "AI-assisted cleanup for authorized edits only." },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><head><meta charSet="utf-8" /></head><body><Providers>{children}</Providers></body></html>;
}