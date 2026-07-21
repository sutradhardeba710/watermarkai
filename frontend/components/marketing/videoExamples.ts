export type VideoExampleCategory = "logo" | "timestamp" | "subtitle" | "overlay" | "branding" | "presentation";
export type VideoExampleMode = "Fast" | "Balanced" | "High Quality";

export type VideoExample = {
  id: string;
  title: string;
  description: string;
  detailedDescription: string;
  category: VideoExampleCategory;
  mode: VideoExampleMode;
  maskType: string;
  originalImage: string;
  cleanedImage: string;
  originalPoster: string;
  cleanedPoster: string;
  thumbnailOriginal: string;
  thumbnailCleaned: string;
  disclaimer: string;
  altOriginal: string;
  altCleaned: string;
};

const asset = (id: string, file: string) => `/examples/${id}/${file}`;

export const videoExamples: VideoExample[] = [
  {
    id: "corner-logo",
    title: "Corner logo",
    description: "Remove a small logo from footage you created or are authorized to edit.",
    detailedDescription: "A fictional CF Studio mark sits over a creator's neutral tutorial set. The fixed region makes a static rectangle the clearest starting point.",
    category: "logo",
    mode: "Balanced",
    maskType: "Static rectangle",
    originalImage: asset("corner-logo", "original.webp"),
    cleanedImage: asset("corner-logo", "cleaned.webp"),
    originalPoster: asset("corner-logo", "original-poster.webp"),
    cleanedPoster: asset("corner-logo", "cleaned-poster.webp"),
    thumbnailOriginal: asset("corner-logo", "thumbnail-original.webp"),
    thumbnailCleaned: asset("corner-logo", "thumbnail-cleaned.webp"),
    disclaimer: "Fictional mark on generated, owned demonstration media.",
    altOriginal: "Generated creator tutorial scene with a fictional CF Studio logo in the top-right corner",
    altCleaned: "The same generated creator tutorial scene without the fictional corner logo",
  },
  {
    id: "timestamp",
    title: "Timestamp",
    description: "Clean a burned-in date and time from your own recorded footage.",
    detailedDescription: "A fictional date, time, and CAM 02 identifier appear on an owner-controlled warehouse entrance recording.",
    category: "timestamp",
    mode: "Fast",
    maskType: "Static mask",
    originalImage: asset("timestamp", "original.webp"),
    cleanedImage: asset("timestamp", "cleaned.webp"),
    originalPoster: asset("timestamp", "original-poster.webp"),
    cleanedPoster: asset("timestamp", "cleaned-poster.webp"),
    thumbnailOriginal: asset("timestamp", "thumbnail-original.webp"),
    thumbnailCleaned: asset("timestamp", "thumbnail-cleaned.webp"),
    disclaimer: "Fictional timestamp on generated, owner-controlled demonstration media.",
    altOriginal: "Generated private warehouse entrance recording with a fictional timestamp and CAM 02 identifier",
    altCleaned: "The same generated warehouse entrance recording without the timestamp and camera identifier",
  },
  {
    id: "subtitle-cleanup",
    title: "Subtitle cleanup",
    description: "Remove custom subtitles from source footage you own.",
    detailedDescription: "A presenter-authored sentence spans the lower third of an educational lesson, calling for a wide, shallow review region.",
    category: "subtitle",
    mode: "High Quality",
    maskType: "Wide lower-third mask",
    originalImage: asset("subtitle-cleanup", "original.webp"),
    cleanedImage: asset("subtitle-cleanup", "cleaned.webp"),
    originalPoster: asset("subtitle-cleanup", "original-poster.webp"),
    cleanedPoster: asset("subtitle-cleanup", "cleaned-poster.webp"),
    thumbnailOriginal: asset("subtitle-cleanup", "thumbnail-original.webp"),
    thumbnailCleaned: asset("subtitle-cleanup", "thumbnail-cleaned.webp"),
    disclaimer: "Custom subtitle on generated educational demonstration media.",
    altOriginal: "Generated instructor lesson with the custom subtitle Today we will review the final workflow",
    altCleaned: "The same generated instructor lesson without the custom subtitle",
  },
  {
    id: "static-overlay",
    title: "Static overlay",
    description: "Remove an outdated graphic from approved marketing footage.",
    detailedDescription: "A fictional Summer Campaign panel covers the lower-right of a generic product demonstration.",
    category: "overlay",
    mode: "Balanced",
    maskType: "Static polygon",
    originalImage: asset("static-overlay", "original.webp"),
    cleanedImage: asset("static-overlay", "cleaned.webp"),
    originalPoster: asset("static-overlay", "original-poster.webp"),
    cleanedPoster: asset("static-overlay", "cleaned-poster.webp"),
    thumbnailOriginal: asset("static-overlay", "thumbnail-original.webp"),
    thumbnailCleaned: asset("static-overlay", "thumbnail-cleaned.webp"),
    disclaimer: "Fictional campaign panel on generated, approved demonstration media.",
    altOriginal: "Generated product demonstration with a fictional Summer Campaign Internal Review panel",
    altCleaned: "The same generated product demonstration without the promotional panel",
  },
  {
    id: "old-branding",
    title: "Old branding",
    description: "Clean outdated branding from internal or client-approved footage.",
    detailedDescription: "A fictional Northstar Media lower third appears over an internal town-hall recording.",
    category: "branding",
    mode: "Balanced",
    maskType: "Lower-third mask",
    originalImage: asset("old-branding", "original.webp"),
    cleanedImage: asset("old-branding", "cleaned.webp"),
    originalPoster: asset("old-branding", "original-poster.webp"),
    cleanedPoster: asset("old-branding", "cleaned-poster.webp"),
    thumbnailOriginal: asset("old-branding", "thumbnail-original.webp"),
    thumbnailCleaned: asset("old-branding", "thumbnail-cleaned.webp"),
    disclaimer: "Fictional identity on generated internal-presentation media.",
    altOriginal: "Generated office town hall with a fictional Northstar Media Internal Presentation lower third",
    altCleaned: "The same generated office town hall without the fictional lower-third branding",
  },
  {
    id: "presentation-badge",
    title: "Presentation badge",
    description: "Remove a static event badge from an approved conference recording.",
    detailedDescription: "A fictional Session 04 badge occupies a fixed upper-left region of a conference presentation.",
    category: "presentation",
    mode: "High Quality",
    maskType: "Static circular mask",
    originalImage: asset("presentation-badge", "original.webp"),
    cleanedImage: asset("presentation-badge", "cleaned.webp"),
    originalPoster: asset("presentation-badge", "original-poster.webp"),
    cleanedPoster: asset("presentation-badge", "cleaned-poster.webp"),
    thumbnailOriginal: asset("presentation-badge", "thumbnail-original.webp"),
    thumbnailCleaned: asset("presentation-badge", "thumbnail-cleaned.webp"),
    disclaimer: "Static fallback example; production-ready moving-mask tracking is not implied.",
    altOriginal: "Generated conference presentation with a fictional circular Session 04 badge",
    altCleaned: "The same generated conference presentation without the circular badge",
  },
];
