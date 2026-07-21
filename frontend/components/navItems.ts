import type { LucideIcon } from "lucide-react";
import { Boxes, CircleHelp, Eye, FileCheck2, Film, Gauge, History, Layers3, LifeBuoy, ScanSearch, ShieldCheck, Sparkles, Users, WandSparkles, Workflow } from "lucide-react";

export type NavLink = { label: string; description: string; href: string; icon: LucideIcon; section?: string };
export type NavGroup = { label: string; links: NavLink[]; columns: 1 | 2; width: "sm" | "lg" };

export const navGroups: NavGroup[] = [
  { label: "Product", columns: 2, width: "lg", links: [
    { label: "Overview", description: "Follow the complete path from upload to reviewed export.", href: "/product", icon: Sparkles },
    { label: "AI Detection", description: "Surface persistent logos, text, timestamps, and overlays for review.", href: "/product/ai-detection", icon: ScanSearch },
    { label: "Manual Masking", description: "Draw, refine, and preview the exact area you want to clean.", href: "/product/manual-masking", icon: Layers3 },
    { label: "Temporal Tracking", description: "Keep approved masks aligned where motion tracking is supported.", href: "/product/temporal-tracking", icon: Workflow },
    { label: "Review & Export", description: "Compare a processed preview before starting the final render.", href: "/product/review-export", icon: FileCheck2 },
    { label: "Video Examples", description: "Explore authorized before-and-after cleanup examples.", href: "/product/examples", icon: Eye },
  ] },
  { label: "Solutions", columns: 2, width: "lg", links: [
    { label: "For Content Creators", description: "Update self-owned branding, timestamps, and archived footage.", href: "/solutions/content-creators", icon: WandSparkles },
    { label: "For Video Editors", description: "Reduce repetitive cleanup without losing editorial control.", href: "/solutions/video-editors", icon: Film },
    { label: "For Agencies / Teams", description: "Standardize a reviewable workflow for licensed client footage.", href: "/solutions/agencies", icon: Users },
    { label: "Authorized Use & Compliance", description: "Understand which footage may be processed and why.", href: "/authorized-use", icon: ShieldCheck },
  ] },
  { label: "Resources", columns: 2, width: "lg", links: [
    { label: "How It Works", description: "See all ten steps from account creation to retention.", href: "/how-it-works", icon: Workflow },
    { label: "FAQ", description: "Answers about masking, quality, credits, files, and privacy.", href: "/faq", icon: CircleHelp },
    { label: "Supported Formats", description: "Review MP4, MOV, WebM, codec, and upload requirements.", href: "/supported-formats", icon: Boxes },
    { label: "Changelog", description: "Follow verified product and platform improvements.", href: "/changelog", icon: History },
    { label: "Help Center", description: "Find billing, upload, policy, and contact routes quickly.", href: "/support", icon: LifeBuoy },
  ] },
];

export const primaryNav = { pricing: { label: "Pricing", description: "Compare live plan prices, credits, and limits.", href: "/pricing", icon: Gauge, section: "pricing" } };
