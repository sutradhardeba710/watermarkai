import type { LucideIcon } from "lucide-react";
import { Eye, FileCheck2, Layers3, ScanSearch, Workflow } from "lucide-react";

export type ProductStoryItem = { title: string; description: string };
export type ProductFeature = {
  slug: string; title: string; shortTitle: string; description: string; benefit: string; href: string;
  icon: LucideIcon; eyebrow: string; bullets: string[];
  primaryCta: { label: string; href: string }; secondaryCta: { label: string; href: string };
  workflowTitle: string; workflowIntro: string; workflow: ProductStoryItem[];
  capabilitiesTitle: string; capabilities: ProductStoryItem[]; examples: ProductStoryItem[]; limitations: string[];
};

export const productFeatures: ProductFeature[] = [
  {
    slug: "ai-detection", title: "Find likely overlays without searching every frame yourself", shortTitle: "AI Detection",
    description: "ClearFrame samples the footage and surfaces persistent logos, subtitles, timestamps, and visual overlays as candidates you can review.",
    benefit: "Useful suggestions, never silent decisions.", href: "/product/ai-detection", icon: ScanSearch, eyebrow: "Review likely regions sooner",
    bullets: ["Confidence-ranked candidates", "Accept, reject, or edit", "Manual masking always available"],
    primaryCta: { label: "Try AI-assisted detection", href: "/signup" }, secondaryCta: { label: "Explore manual masking", href: "/product/manual-masking" },
    workflowTitle: "From sampled frames to an editable mask.", workflowIntro: "Detection narrows the search. It does not start processing or approve a region on your behalf.",
    workflow: [
      { title: "Prepare a proxy", description: "Read the video metadata and create a practical review copy." },
      { title: "Sample frames", description: "Inspect representative points without requiring you to scrub the entire timeline." },
      { title: "Generate candidates", description: "Look for repeated text, static marks, and low-motion foreground regions." },
      { title: "Rank suggestions", description: "Order candidates by confidence and show why each region needs review." },
      { title: "Review", description: "Accept, reject, retry, or switch to manual selection." },
      { title: "Refine the mask", description: "Continue with Rectangle, Polygon, Brush, or Eraser controls." },
    ],
    capabilitiesTitle: "What the detector is designed to surface.",
    capabilities: [
      { title: "Persistent text", description: "Timestamps, custom subtitles, and text overlays that remain in a similar area." },
      { title: "Static logos", description: "Self-owned channel marks and internal branding anchored to the frame." },
      { title: "Semi-transparent overlays", description: "Low-opacity regions that may need closer manual review." },
      { title: "Low-motion foreground elements", description: "Visual regions that change less than the scene behind them." },
    ],
    examples: [
      { title: "Strong match", description: "A persistent, clearly bounded region that appears across sampled frames." },
      { title: "Possible match", description: "A plausible overlay with enough uncertainty to deserve a closer look." },
      { title: "Low confidence", description: "A weak or inconsistent signal. Manual review is required." },
      { title: "No confident result", description: "Nothing reliable was found; draw the region manually or retry." },
    ],
    limitations: ["Scene complexity and fast visual changes can reduce detection quality.", "Transparent or moving overlays can be harder to isolate.", "Text that belongs to the scene may be suggested incorrectly.", "Every candidate should be reviewed before it becomes a mask."],
  },
  {
    slug: "manual-masking", title: "Mark the exact area that needs attention", shortTitle: "Manual Masking",
    description: "Start from a detection suggestion or create the selection yourself with rectangle, polygon, brush, and eraser tools.",
    benefit: "Precise control when the footage needs it.", href: "/product/manual-masking", icon: Layers3, eyebrow: "Shape the cleanup area yourself",
    bullets: ["Rectangle, Polygon, Brush, and Eraser", "Expansion and feather controls", "Undo, reset, and preview"],
    primaryCta: { label: "Create a precise mask", href: "/signup" }, secondaryCta: { label: "See how tracking works", href: "/product/temporal-tracking" },
    workflowTitle: "A workspace built around the frame, not a form.", workflowIntro: "Draw directly on the video, tune the edge, inspect the timeline, and save only when the selection looks right.",
    workflow: [
      { title: "Choose a tool", description: "Use Rectangle for fixed marks, Polygon for hard edges, or Brush for irregular areas." },
      { title: "Draw on the frame", description: "Place the selection around the visible overlay and use zoom or pan for detail." },
      { title: "Correct the shape", description: "Add with Brush, remove with Eraser, or use undo and redo." },
      { title: "Tune the edge", description: "Expand or shrink the region and feather its boundary to reduce seams." },
      { title: "Review nearby frames", description: "Check the selection on bright, dark, and visually busy moments." },
      { title: "Save and preview", description: "Generate a short result before the full processing job." },
    ],
    capabilitiesTitle: "The right tool for the shape in front of you.",
    capabilities: [
      { title: "Rectangle", description: "Fast selection for corner logos, timestamps, and other fixed regions." },
      { title: "Polygon", description: "Point-by-point control around sharp or angled graphics." },
      { title: "Brush and Eraser", description: "Paint irregular areas, then remove any part that extends too far." },
      { title: "Mask properties", description: "Adjust expansion, feathering, brush controls, and temporal smoothing." },
    ],
    examples: [
      { title: "Corner logo", description: "Use a small rectangular mask with a slight expansion beyond the visible edge." },
      { title: "Timestamp", description: "Check several timestamps so changing digits remain inside the selection." },
      { title: "Subtitle line", description: "Use a wide, shallow region and verify it does not cover scene text you want to keep." },
      { title: "Irregular graphic", description: "Combine Polygon and Brush for shapes that do not fit a clean rectangle." },
    ],
    limitations: ["The current MVP applies the saved mask across the full video; custom time ranges are not yet a separate processing mode.", "Extend the mask slightly beyond visible edges, but avoid covering nearby details.", "Feathering can reduce seams, but it cannot repair a poorly positioned mask.", "Reset and redraw are always available before processing begins."],
  },
  {
    slug: "temporal-tracking", title: "Keep the selected region aligned as the footage changes", shortTitle: "Temporal Tracking",
    description: "ClearFrame can propagate approved regions across nearby frames and surface alignment problems for review where tracking is supported.",
    benefit: "Less repetitive correction, with review points kept visible.", href: "/product/temporal-tracking", icon: Workflow, eyebrow: "Follow motion without hiding uncertainty",
    bullets: ["Static-mask baseline", "Temporal smoothing", "Review points for motion and cuts"],
    primaryCta: { label: "Review a tracked mask", href: "/signup" }, secondaryCta: { label: "See preview and export", href: "/product/review-export" },
    workflowTitle: "Tracking is a review aid, not a guarantee.", workflowIntro: "The current product starts with a dependable full-video static mask. Motion-aware propagation is used only where the available tracking path supports it.",
    workflow: [
      { title: "Approve the region", description: "Start from a detection candidate or a manually drawn mask." },
      { title: "Establish a reference", description: "Use the approved frame as the anchor for nearby comparisons." },
      { title: "Analyze motion", description: "Compare local movement and stable visual features around the selected region." },
      { title: "Propagate carefully", description: "Move the mask across supported neighboring frames without changing its purpose." },
      { title: "Flag uncertainty", description: "Surface scene cuts, low confidence, and possible lost alignment for review." },
      { title: "Correct and smooth", description: "Add a correction point or use temporal smoothing to reduce visible jitter." },
    ],
    capabilitiesTitle: "Three region behaviors, three different expectations.",
    capabilities: [
      { title: "Fixed mask", description: "Best for an overlay that stays anchored to the same frame coordinates." },
      { title: "Moving region", description: "Requires a supported tracking pass and review as the scene moves." },
      { title: "Scene-based change", description: "Cuts and major composition shifts often need a fresh reference or manual correction." },
      { title: "Temporal smoothing", description: "Reduces small frame-to-frame changes that would otherwise read as mask jitter." },
    ],
    examples: [
      { title: "Stable corner mark", description: "A full-video static mask is usually the simplest and most predictable path." },
      { title: "Slow camera pan", description: "Motion analysis may keep a supported tracked region aligned across nearby frames." },
      { title: "Scene cut", description: "Treat the cut as a review point rather than carrying the old position forward blindly." },
      { title: "Temporary overlay", description: "Check when the graphic appears and disappears; the current MVP still saves a full-video mask." },
    ],
    limitations: ["Fast camera movement, motion blur, and occlusion can reduce alignment quality.", "Major scene changes and complex backgrounds often need manual correction.", "Moving overlays are not supported equally by every processing path.", "The current MVP persists a full-video static mask even when a custom range is recorded."],
  },
  {
    slug: "review-export", title: "Review the result before committing to the full render", shortTitle: "Review & Export",
    description: "Generate a short preview, compare it with the original, and continue only when the selected area looks right.",
    benefit: "A deliberate quality gate before credits fund the full job.", href: "/product/review-export", icon: FileCheck2, eyebrow: "Compare before you process",
    bullets: ["Short preview generation", "Accessible before-and-after review", "Signed output download"],
    primaryCta: { label: "Generate a preview", href: "/signup" }, secondaryCta: { label: "View pricing", href: "/pricing" },
    workflowTitle: "Spend a minute reviewing before spending a full job.", workflowIntro: "The preview stage gives you a smaller, reviewable result so you can change the mask or settings before full processing.",
    workflow: [
      { title: "Save the mask", description: "Confirm that the selection and edge settings are ready for a sample." },
      { title: "Choose a preview point", description: "Select a representative part of the footage rather than an easy frame." },
      { title: "Generate the preview", description: "Render a short comparison using the selected processing preset." },
      { title: "Compare", description: "Use the split view and playback controls to inspect seams, missed pixels, and scene detail." },
      { title: "Adjust if needed", description: "Return to the mask workspace without losing the project context." },
      { title: "Start full processing", description: "Review the credit estimate, approve the job, and monitor queue progress." },
      { title: "Download or retry", description: "Use the temporary signed link, or reprocess after changing settings." },
    ],
    capabilitiesTitle: "A comparison view built for an actual decision.",
    capabilities: [
      { title: "Split slider", description: "Drag the divider or use arrow keys to compare the same frame." },
      { title: "Playback review", description: "Loop the preview and inspect the result over time instead of judging one still." },
      { title: "Output preservation", description: "Retain aspect ratio and frame rate where possible; preserve audio or transcode it to AAC when required." },
      { title: "Credit transparency", description: "Show the remaining balance and the server-authoritative 100-credit processing cost before starting." },
    ],
    examples: [
      { title: "Split view", description: "Best for comparing edge detail at the same moment." },
      { title: "Side by side", description: "Useful when the affected area is small and both full frames matter." },
      { title: "Original only", description: "Confirm exactly what the overlay covered before judging the reconstruction." },
      { title: "Processed only", description: "Look for flicker, repeated texture, or soft edges without the original competing for attention." },
    ],
    limitations: ["Results vary with movement, texture, overlay opacity, and the content hidden beneath the selected area.", "Failed processing jobs are refunded by the credit ledger when the job failure path completes.", "Outputs use H.264 video and AAC audio by default; incompatible source audio may be transcoded.", "Signed download links expire, and stored artifacts follow configured retention windows."],
  },
  {
    slug: "examples", title: "See how different cleanup decisions look in context", shortTitle: "Video Examples",
    description: "Explore authorized demonstration scenes for static marks, timestamps, custom subtitles, and supported moving regions.",
    benefit: "Varied examples with the limitations left visible.", href: "/product/examples", icon: Eye, eyebrow: "Authorized demonstration footage",
    bullets: ["Multiple distinct scenes", "Original and processed views", "Preset and mask notes"],
    primaryCta: { label: "Try with your footage", href: "/signup" }, secondaryCta: { label: "How ClearFrame works", href: "/how-it-works" },
    workflowTitle: "Read each result in the context of the source.", workflowIntro: "Examples show the editing decision, the selected mask behavior, and the factors that can change the outcome.",
    workflow: [
      { title: "Choose a scene", description: "Filter by static or moving region, text type, and quality preset." },
      { title: "Inspect the original", description: "See the location and shape of the demonstration overlay." },
      { title: "Compare the result", description: "Review the processed region without implying the rest of the scene changed." },
      { title: "Read the mask note", description: "Understand whether the example uses a static mask or a supported tracked path." },
      { title: "Check the limitation", description: "Look for transparency, movement, texture, and scene changes that affect quality." },
    ],
    capabilitiesTitle: "Examples are guidance, not benchmark claims.",
    capabilities: [
      { title: "Owned corner logo", description: "A fixed brand mark on demonstration footage created for the product." },
      { title: "Timestamp cleanup", description: "Changing digits inside a consistent frame region." },
      { title: "Custom subtitle", description: "A user-created text line removed from its original source file." },
      { title: "Internal branding", description: "Outdated graphics on approved company or client footage." },
    ], examples: [],
    limitations: ["The gallery uses authored demonstration scenes rather than third-party branded footage.", "No processing-time claims are shown because those require measured jobs and hardware context.", "Moving examples apply only to supported tracking paths.", "Results vary with the footage, mask, preset, and content hidden beneath the overlay."],
  },
];

export const productFeatureBySlug = new Map(productFeatures.map((feature) => [feature.slug, feature]));
