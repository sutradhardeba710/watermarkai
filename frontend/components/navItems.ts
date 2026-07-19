import type { LucideIcon } from "lucide-react";
import { Boxes, CircleHelp, Eye, FileCheck2, Film, Gauge, History, Layers3, ScanSearch, ShieldCheck, Sparkles, Users, WandSparkles, Workflow } from "lucide-react";

export type NavLink = { label: string; description: string; href: string; icon: LucideIcon; section?: string };
export type NavGroup = { label: string; links: NavLink[]; columns: 1 | 2; width: "sm" | "lg" };

export const navGroups: NavGroup[] = [
  { label: "Product", columns: 2, width: "lg", links: [
    { label: "Overview", description: "A clear path from footage to finished export.", href: "/product", icon: Sparkles },
    { label: "AI Detection", description: "Find logos, overlays, and timestamps faster.", href: "/product/ai-detection", icon: ScanSearch },
    { label: "Manual Masking", description: "Keep precise control over every frame.", href: "/product/manual-masking", icon: Layers3 },
    { label: "Temporal Tracking", description: "Keep masks aligned through movement and cuts.", href: "/product/temporal-tracking", icon: Workflow },
    { label: "Review & Export", description: "Approve a preview before the full render.", href: "/product/review-export", icon: FileCheck2 },
    { label: "Video examples", description: "Compare authorized before-and-after footage.", href: "/#demo", icon: Eye, section: "demo" },
  ] },
  { label: "Solutions", columns: 2, width: "lg", links: [
    { label: "For Content Creators", description: "Polish footage you made and own.", href: "/solutions/content-creators", icon: WandSparkles },
    { label: "For Video Editors", description: "Move quickly without losing judgment.", href: "/solutions/video-editors", icon: Film },
    { label: "For Agencies / Teams", description: "A reviewable workflow for client work.", href: "/solutions/agencies", icon: Users },
    { label: "Authorized Use & Compliance", description: "Clear guardrails for legitimate edits.", href: "/authorized-use", icon: ShieldCheck },
  ] },
  { label: "Resources", columns: 2, width: "lg", links: [
    { label: "How it works", description: "Understand the complete four-step workflow.", href: "/how-it-works", icon: Workflow },
    { label: "FAQ", description: "Answers about processing, quality, and authorization.", href: "/faq", icon: CircleHelp },
    { label: "Supported Formats", description: "MP4, MOV, WebM, and media requirements.", href: "/supported-formats", icon: Boxes },
    { label: "Changelog", description: "Follow meaningful product improvements.", href: "/changelog", icon: History },
  ] },
];

export const primaryNav = { pricing: { label: "Pricing", description: "Compare processing plans.", href: "/pricing", icon: Gauge, section: "pricing" } };