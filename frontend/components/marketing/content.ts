import type { LucideIcon } from "lucide-react";
import {
  Boxes,
  Brush,
  Building2,
  Clapperboard,
  Download,
  Eye,
  Film,
  GraduationCap,
  History,
  Layers,
  Megaphone,
  MonitorPlay,
  ScanSearch,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Upload,
  Wand2,
} from "lucide-react";

// --- Workflow (the six real pipeline stages) ---
export type WorkflowStepData = {
  n: string;
  title: string;
  copy: string;
  icon: LucideIcon;
};

export const workflowSteps: WorkflowStepData[] = [
  { n: "01", title: "Upload", copy: "Add an MP4, MOV, or supported video from your device.", icon: Upload },
  { n: "02", title: "Detect", copy: "Let ClearFrame identify persistent logos, text, and overlays.", icon: ScanSearch },
  { n: "03", title: "Mask", copy: "Approve the suggestion or edit the selected area manually.", icon: Brush },
  { n: "04", title: "Track", copy: "Review how the selected region follows the footage.", icon: Layers },
  { n: "05", title: "Preview", copy: "Compare a short processed result before using full credits.", icon: Eye },
  { n: "06", title: "Export", copy: "Render and download the cleaned video with audio preserved.", icon: Download },
];

// --- Benefits ---
export type BenefitData = { title: string; copy: string; icon: LucideIcon };

export const benefits: BenefitData[] = [
  { title: "AI-assisted detection", copy: "ClearFrame suggests likely logos, text, timestamps, and visual overlays.", icon: ScanSearch },
  { title: "Manual precision", copy: "Resize, redraw, brush, erase, feather, and review the mask yourself.", icon: SlidersHorizontal },
  { title: "Preview before processing", copy: "Test a short section before committing credits to the full render.", icon: Eye },
  { title: "Original output preserved", copy: "Maintain aspect ratio, frame rate, audio, and video synchronization where possible.", icon: ShieldCheck },
];

// --- Use cases ---
export type UseCaseData = { title: string; copy: string; icon: LucideIcon };

export const useCases: UseCaseData[] = [
  { title: "Content creators", copy: "Remove your previous channel logo or an old timestamp from footage you own.", icon: Wand2 },
  { title: "Video editors", copy: "Clean approved source footage without losing frame-level judgment.", icon: Film },
  { title: "Marketing teams", copy: "Update approved campaign footage when branding changes.", icon: Megaphone },
  { title: "Businesses", copy: "Clean internal recordings containing outdated overlays.", icon: Building2 },
  { title: "Education teams", copy: "Remove your own subtitles, course labels, or timestamps.", icon: GraduationCap },
  { title: "Media restoration", copy: "Reduce persistent overlays on archival footage you are authorized to edit.", icon: History },
];

// --- Quality comparison ---
export const basicRemoverPoints = [
  "Blur or pixelate the region",
  "Crop or zoom away detail",
  "Cover with a solid block",
  "Visible artifacts left behind",
  "No frame-by-frame review",
];

export const clearFramePoints = [
  "AI-assisted overlay detection",
  "Editable, frame-accurate mask",
  "Timeline review across the clip",
  "Temporal smoothing for stability",
  "Preview-first, credit-safe workflow",
  "Audio-preserving export",
];

// --- Feature grid (<=6 real features) ---
export type FeatureData = { title: string; copy: string; icon: LucideIcon; href?: string };

export const features: FeatureData[] = [
  { title: "AI-assisted overlay detection", copy: "Surface persistent logos, subtitles, timestamps, and overlays for your review.", icon: ScanSearch, href: "/product/ai-detection" },
  { title: "Rectangle, polygon, brush, eraser", copy: "Shape the mask exactly around the area you want to clean.", icon: Brush, href: "/product/manual-masking" },
  { title: "Static and moving tracking", copy: "Keep the selection aligned as the footage and overlay move.", icon: Layers, href: "/product/temporal-tracking" },
  { title: "Short preview generation", copy: "Render a brief section first so you commit credits with confidence.", icon: Eye, href: "/product/review-export" },
  { title: "Before / after comparison", copy: "Inspect the original and cleaned result side by side before export.", icon: MonitorPlay, href: "/#proof" },
  { title: "Secure temporary storage", copy: "Private storage with signed downloads and automatic file expiration.", icon: ShieldCheck, href: "/authorized-use" },
];

// --- Trust principles ---
export type TrustPrinciple = { title: string; copy: string; icon: LucideIcon };

export const trustPrinciples: TrustPrinciple[] = [
  { title: "Authorized-use confirmation", copy: "You confirm you own or are licensed to edit the footage before processing.", icon: ShieldCheck },
  { title: "Private storage", copy: "Uploads are kept private to your account, never shown publicly.", icon: Boxes },
  { title: "Temporary signed access", copy: "Media plays and downloads through short-lived signed links only.", icon: Eye },
  { title: "Automatic file expiration", copy: "Source, preview, and output files are removed on a configured schedule.", icon: History },
];

// --- Example categories (uses the 2 real demo images; labelled illustrative) ---
export type ExampleData = {
  id: string;
  label: string;
  removed: string;
  mode: "Balanced" | "High";
};

export const examples: ExampleData[] = [
  { id: "logo", label: "Corner logo", removed: "A static channel logo in the corner of the frame.", mode: "Balanced" },
  { id: "timestamp", label: "Timestamp", removed: "A burned-in date and time overlay.", mode: "Balanced" },
  { id: "subtitle", label: "Subtitle cleanup", removed: "Hard-coded subtitles along the lower third.", mode: "High" },
  { id: "overlay", label: "Static overlay", removed: "A persistent graphic overlay on the footage.", mode: "High" },
];

// --- FAQ (categorized; feeds visible FAQ + JSON-LD) ---
export type FaqCategory = "Product" | "Processing" | "Credits & billing" | "Privacy" | "Authorized use";
export type FaqItem = { q: string; a: string; category: FaqCategory };

export const faqItems: FaqItem[] = [
  { category: "Product", q: "What can an AI video watermark remover remove?", a: "ClearFrame is built to remove persistent visual overlays — including your own logos, watermarks, timestamps, hardcoded subtitles, and static graphics — from footage you own or are authorized to edit." },
  { category: "Product", q: "Can I remove a logo or timestamp from an MP4 video?", a: "Yes. Upload an MP4, MOV, or WebM video, let ClearFrame suggest the logo or timestamp region, refine the mask if needed, and generate a short preview before processing the full video." },
  { category: "Product", q: "Can ClearFrame remove hardcoded subtitles from a video?", a: "Yes, when the subtitles are burned into the picture on footage you are authorized to edit. Select the subtitle region, preview the reconstructed area, and check detailed backgrounds or moving subjects carefully before export." },
  { category: "Product", q: "Can it remove moving overlays?", a: "Yes, ClearFrame supports tracking a selected region as it moves. Results vary with speed, occlusion, and how much the background changes behind the overlay." },
  { category: "Processing", q: "Will every video produce a perfect result?", a: "No. Quality depends on scene complexity, movement, mask accuracy, and source quality. That is exactly why you preview a short section before running the full render." },
  { category: "Processing", q: "What video formats are supported?", a: "MP4, MOV, and WebM uploads are supported, subject to the product's validation limits for size, duration, and resolution." },
  { category: "Processing", q: "Is audio preserved?", a: "The workflow is designed to preserve original audio, resolution, frame rate, aspect ratio, and duration where technically possible." },
  { category: "Credits & billing", q: "Does previewing use credits?", a: "No. Generating a short preview is free. Credits are only used when you run a full-resolution render." },
  { category: "Credits & billing", q: "What happens if processing fails?", a: "If a full render fails, the credits for that job are returned to your balance so you are not charged for an incomplete result." },
  { category: "Credits & billing", q: "What happens to unused credits?", a: "Daily credits reset every 24 hours and do not roll over. You can move to a plan with a larger allowance at any time." },
  { category: "Credits & billing", q: "Can I cancel my subscription?", a: "Yes. You can cancel from your billing settings at any time and keep access until the end of the current period." },
  { category: "Privacy", q: "How long are files stored?", a: "Files are retained only for the workflow and removed on a configured retention schedule. Source, preview, and output files each have their own window." },
  { category: "Privacy", q: "Can ClearFrame access my video publicly?", a: "No. Your uploads stay private to your account and are only served through short-lived signed links for playback and download." },
  { category: "Authorized use", q: "Can I remove a watermark from any video?", a: "No. ClearFrame is for footage you own, license, or are authorized to edit. Removing third-party ownership marks, paid stock watermarks, or DRM-protected content is prohibited." },
];

// --- Plan target-user copy (keyed by plan id) ---
export const planTargetCopy: Record<string, string> = {
  free: "For testing the workflow on short clips.",
  starter: "For creators who clean videos regularly.",
  pro: "For professionals processing larger or higher-quality footage.",
};

export const heroTrust = [
  "No credit card required",
  "Manual control included",
  "Preview before processing",
];

export const marketingIcons = { Sparkles, Clapperboard, Upload, Download };
