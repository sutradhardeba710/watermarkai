export type FooterLink = { label: string; href: string };
export type FooterColumnConfig = { title: string; links: FooterLink[] };

export const footerColumns: FooterColumnConfig[] = [
  { title: "Product", links: [
    { label: "Overview", href: "/product" }, { label: "AI Detection", href: "/product/ai-detection" }, { label: "Manual Masking", href: "/product/manual-masking" }, { label: "Temporal Tracking", href: "/product/temporal-tracking" }, { label: "Review & Export", href: "/product/review-export" }, { label: "Video Examples", href: "/product/examples" }, { label: "Pricing", href: "/pricing" },
  ] },
  { title: "Solutions", links: [
    { label: "For Content Creators", href: "/solutions/content-creators" }, { label: "For Video Editors", href: "/solutions/video-editors" }, { label: "For Agencies / Teams", href: "/solutions/agencies" }, { label: "Authorized Use", href: "/authorized-use" },
  ] },
  { title: "Resources", links: [
    { label: "How It Works", href: "/how-it-works" }, { label: "FAQ", href: "/faq" }, { label: "Supported Formats", href: "/supported-formats" }, { label: "Changelog", href: "/changelog" }, { label: "Help Center", href: "/support" },
  ] },
  { title: "Company / Legal", links: [
    { label: "About", href: "/about" }, { label: "Contact", href: "/contact" }, { label: "Terms of Service", href: "/terms" }, { label: "Privacy Policy", href: "/privacy" }, { label: "Acceptable Use", href: "/acceptable-use" }, { label: "Security", href: "/security" },
  ] },
];

export const footerTrustBadges = ["Authorized use only", "Preview before full render", "No DRM removal", "MP4 · MOV · WebM"];
