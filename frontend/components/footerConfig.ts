import type { LucideIcon } from "lucide-react";
import { AtSign, Code, Play, Users } from "lucide-react";

export type FooterLink = { label: string; href: string };
export type FooterColumnConfig = { title: string; links: FooterLink[] };
export type FooterSocial = { label: string; href: string; icon: LucideIcon };

export const footerColumns: FooterColumnConfig[] = [
  { title: "Product", links: [
    { label: "Overview", href: "/product" }, { label: "AI Detection", href: "/product/ai-detection" }, { label: "Manual Masking", href: "/product/manual-masking" }, { label: "Temporal Tracking", href: "/product/temporal-tracking" }, { label: "Review & Export", href: "/product/review-export" }, { label: "Pricing", href: "/pricing" },
  ] },
  { title: "Solutions", links: [
    { label: "For Content Creators", href: "/solutions/content-creators" }, { label: "For Video Editors", href: "/solutions/video-editors" }, { label: "For Agencies / Teams", href: "/solutions/agencies" }, { label: "Authorized Use & Compliance", href: "/authorized-use" },
  ] },
  { title: "Resources", links: [
    { label: "How it works", href: "/how-it-works" }, { label: "FAQ", href: "/faq" }, { label: "Supported Formats", href: "/supported-formats" }, { label: "Changelog", href: "/changelog" },
  ] },
  { title: "Company / Legal", links: [
    { label: "About", href: "/about" }, { label: "Contact", href: "/contact" }, { label: "Terms of Service", href: "/terms" }, { label: "Privacy Policy", href: "/privacy" }, { label: "Acceptable Use Policy", href: "/acceptable-use" }, { label: "Security", href: "/security" },
  ] },
];

export const footerSocials: FooterSocial[] = [
  { label: "X / Twitter", href: "https://x.com", icon: AtSign },
  { label: "YouTube", href: "https://youtube.com", icon: Play },
  { label: "LinkedIn", href: "https://linkedin.com", icon: Users },
  { label: "GitHub", href: "https://github.com", icon: Code },
];

export const footerTrustBadges = ["Authorized use only", "Original audio preserved", "No DRM removal", "MP4 · MOV · WebM"];