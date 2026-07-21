export type SeoEntry = { title: string; body: string; bullets?: string[]; status?: string };
export type SeoSection = { id: string; title: string; body?: string; bullets?: string[]; entries?: SeoEntry[] };
export type SeoPageKind = "workflow" | "creator" | "editor" | "agency" | "compliance" | "formats" | "faq" | "changelog" | "about" | "legal" | "status";
export type SeoPage = {
  slug: string[]; title: string; description: string; eyebrow: string; heading: string; intro: string;
  kind: SeoPageKind; sections: SeoSection[]; cta: { label: string; href: string; title: string; body: string };
  lastUpdated?: string;
};

export const seoPages: SeoPage[] = [
  {
    slug: ["how-it-works"], title: "How ClearFrame Works", description: "Follow the complete ClearFrame workflow from account creation and authorized upload to mask review, preview, processing, download, and deletion.",
    eyebrow: "Complete visual guide", heading: "A reviewable path from authorized footage to finished output.",
    intro: "ClearFrame keeps the upload, detection, mask, preview, processing, and retention decisions in one connected project instead of hiding them behind a single button.", kind: "workflow",
    sections: [
      { id: "prepare", title: "Prepare the project", entries: [
        { title: "Create an account", body: "Register, verify your email, and open the project dashboard." },
        { title: "Upload authorized footage", body: "Choose an MP4, MOV, or WebM file you own or are permitted to modify, then confirm that authorization." },
        { title: "Analyze the video", body: "ClearFrame validates the container and records duration, dimensions, frame rate, codecs, and file integrity before editing begins." },
      ] },
      { id: "select", title: "Find and define the region", entries: [
        { title: "Review detection", body: "Inspect ranked candidates for persistent logos, timestamps, subtitles, and overlays. Accept, reject, retry, or switch to manual selection." },
        { title: "Create or refine the mask", body: "Use Rectangle, Polygon, Brush, and Eraser controls, then tune expansion and feathering." },
        { title: "Review tracking", body: "Use the static-mask baseline or inspect motion-aware propagation where supported. Scene changes and low confidence remain review points." },
      ] },
      { id: "finish", title: "Preview, process, and retain", entries: [
        { title: "Generate a preview", body: "Render a short representative sample and compare the original with the processed result." },
        { title: "Start full processing", body: "Review the server-authoritative credit cost, approve the job, and follow queue and encoding status." },
        { title: "Download the output", body: "Use a temporary signed link for the H.264/AAC result after the job completes." },
        { title: "Delete or retain the project", body: "Remove the project yourself or allow configured retention rules to expire originals, previews, failed artifacts, and outputs." },
      ] },
    ],
    cta: { label: "Create your first project", href: "/signup", title: "See the workflow with your own footage.", body: "Start on the Free plan and review the mask and preview before any full processing job." },
  },
  {
    slug: ["solutions", "content-creators"], title: "Video Cleanup for Content Creators", description: "A creator-focused workflow for updating self-owned branding, timestamps, subtitles, and archived footage with visible review controls.",
    eyebrow: "For content creators", heading: "Give your own archive a cleaner second life.",
    intro: "Update old channel branding, remove creator-added timestamps or subtitles, and prepare footage for a new format without giving up control of the selected region.", kind: "creator",
    sections: [
      { id: "use-cases", title: "Creator use cases", entries: [
        { title: "Replace old channel branding", body: "Clean a self-owned corner logo before applying your current identity." },
        { title: "Reuse archived videos", body: "Remove a timestamp, custom subtitle, or presentation overlay from footage you created." },
        { title: "Prepare new cuts", body: "Create a neutral source before reframing an approved clip for another platform." },
      ] },
      { id: "workflow", title: "A creator-friendly workflow", bullets: ["Open one project per source file", "Let detection narrow the search", "Refine the selected area in the mask editor", "Preview a representative moment", "Approve the full render only when it looks right"] },
      { id: "plans", title: "Credits, privacy, and expectations", entries: [
        { title: "Plan guidance", body: "Free is designed for trying the complete review flow. Starter and Pro add daily capacity and priority according to live plan data." },
        { title: "Private media handling", body: "Projects use authenticated access, controlled storage paths, signed downloads, and configured cleanup windows." },
        { title: "Honest quality expectations", body: "Flat backgrounds and stable marks are often easier than moving, transparent overlays or detailed texture. Results vary, so preview first." },
      ] },
    ],
    cta: { label: "Create your first project", href: "/signup", title: "Bring one owned clip and test the complete review flow.", body: "No card is required for the Free plan." },
  },
  {
    slug: ["solutions", "video-editors"], title: "ClearFrame for Video Editors", description: "Reduce repetitive overlay cleanup with detection review, precise manual masking, preview generation, processing presets, and project history.",
    eyebrow: "For video editors", heading: "Reduce repetitive cleanup without surrendering editorial judgment.",
    intro: "Use assisted detection as a starting point, shape the mask yourself, and make the preview the approval gate before a client-approved source enters full processing.", kind: "editor",
    sections: [
      { id: "timeline", title: "Client-approved footage → Mask → Preview → Review → Export", entries: [
        { title: "Client-approved footage", body: "Document that the source can be modified before it enters the project." },
        { title: "Mask", body: "Accept a detection candidate or draw a rectangle, polygon, or brushed selection." },
        { title: "Preview", body: "Generate a short sample using the selected quality preset." },
        { title: "Review", body: "Inspect edge continuity, hidden texture, movement, and audio/video synchronization." },
        { title: "Export", body: "Queue the approved full render and download through a controlled link." },
      ] },
      { id: "editor-controls", title: "Controls that support an editing workflow", bullets: ["Confidence-ranked candidates instead of an automatic final mask", "Expansion and feathering for edge control", "Temporal smoothing to reduce mask jitter", "Fast, Balanced, and High Quality presets where configured", "Project status and result history", "Reprocess after changing the mask or settings"] },
      { id: "source-preservation", title: "Source characteristics", body: "ClearFrame retains the source aspect ratio and frame rate where the processing path allows, writes H.264 video, and preserves compatible audio or transcodes it to AAC when needed." },
    ],
    cta: { label: "Add ClearFrame to your workflow", href: "/signup", title: "Use the preview as your approval gate.", body: "Test a representative section before committing the complete source." },
  },
  {
    slug: ["solutions", "agencies"], title: "ClearFrame for Agencies and Teams", description: "A controlled, reviewable video cleanup workflow for agencies handling licensed client footage, with a clear distinction between current and planned team features.",
    eyebrow: "For agencies and teams", heading: "Standardize the review path before you standardize the workspace.",
    intro: "ClearFrame can organize projects, processing status, credits, and compliance notes today. Multi-user workspaces and shared team administration are not presented as available before they exist.", kind: "agency",
    sections: [
      { id: "available", title: "Available now", entries: [
        { title: "Central project history", body: "Keep source details, status, previews, and results visible within the account." },
        { title: "Controlled processing", body: "Use the same detect, mask, preview, approve, and export path across client projects." },
        { title: "Subscription and credit visibility", body: "See the active plan, daily balance, and transaction history supported by the account." },
        { title: "Internal compliance records", body: "Authorization confirmations, file hashes, audit metadata, and administrative notes support review." },
      ] },
      { id: "planned", title: "Planned for team workspaces", entries: [
        { title: "Multi-user workspace roles", body: "Planned; not currently available as a customer-facing team workspace.", status: "Planned" },
        { title: "Shared billing and pooled credits", body: "Planned; current credits belong to the active account and plan.", status: "Planned" },
        { title: "Client approval links", body: "Planned; current preview review happens inside the authenticated project workflow.", status: "Planned" },
      ] },
      { id: "agency-fit", title: "When the current product fits", body: "The present workflow fits an agency operator managing authorized files through one controlled account. If your process requires separate client roles or shared billing, contact us before assuming those controls exist." },
    ],
    cta: { label: "Contact us about agency use", href: "/contact", title: "Tell us how your review process works.", body: "We will separate what the current product supports from capabilities that are still planned." },
  },
  {
    slug: ["authorized-use"], title: "Authorized Use and Compliance", description: "Understand which videos ClearFrame may process, which uses are prohibited, and how ownership confirmation, audit metadata, private storage, and retention controls support compliance.",
    eyebrow: "Authorized use", heading: "A useful editing tool needs a clear boundary.",
    intro: "ClearFrame is for footage you created, own, licensed for modification, or have explicit permission to edit. The rules are written to be understood before upload, not discovered after a problem.", kind: "compliance",
    sections: [
      { id: "allowed", title: "Allowed", bullets: ["Your own logo on your own footage", "A timestamp created by your camera or workflow", "Client-approved branding covered by your agreement", "Licensed archive footage that permits modification", "Public-domain footage"] },
      { id: "not-allowed", title: "Not allowed", bullets: ["Stock-preview watermarks", "Third-party ownership logos", "DRM-protected or access-controlled content", "Unauthorized attribution removal", "Downloaded videos you do not have editing rights to"] },
      { id: "safeguards", title: "Workflow safeguards", entries: [
        { title: "Ownership confirmation", body: "You must confirm the authorization basis before uploading a file." },
        { title: "Hashes and audit metadata", body: "File fingerprints, project events, status changes, and administrative actions support traceability." },
        { title: "Account restrictions", body: "Projects or accounts may be limited when reported content or activity crosses the permitted boundary." },
        { title: "Abuse reporting", body: "Compliance reports can be reviewed by authorized administrators and linked to project controls." },
      ] },
      { id: "privacy", title: "Storage and model-use boundary", bullets: ["Private storage paths and authenticated project access", "Temporary signed output links", "Automatic cleanup based on configured retention windows", "No DRM or technical-protection circumvention", "No model training on uploaded videos without explicit opt-in"] },
    ],
    cta: { label: "Read the Acceptable Use Policy", href: "/acceptable-use", title: "Need the policy wording?", body: "Read the complete permitted-use, prohibited-use, enforcement, and reporting terms." },
  },
  {
    slug: ["supported-formats"], title: "Supported Video Formats", description: "Review ClearFrame support for MP4, MOV, WebM, codecs, upload limits, frame rates, rotation metadata, common errors, and H.264/AAC output.",
    eyebrow: "Compatibility guide", heading: "Know what the uploader checks before you begin.",
    intro: "ClearFrame validates the file container and its actual media streams. Changing a filename extension does not convert an unsupported video.", kind: "formats",
    sections: [
      { id: "containers", title: "Current MVP containers", entries: [
        { title: "MP4", body: "Supported. H.264 video with AAC audio is the most predictable upload combination." },
        { title: "MOV", body: "Supported through the MP4/MOV container family. Compatible video and audio streams are inspected after upload." },
        { title: "WebM", body: "Supported. Opus or Vorbis audio may be transcoded to AAC for the MP4 output." },
      ] },
      { id: "limits", title: "Platform validation defaults", bullets: ["Maximum file size: 500 MB unless the live plan config sets a lower plan limit", "Maximum duration: 5 minutes", "Maximum resolution: 1920 × 1080", "Maximum frame rate: 60 fps", "Files must contain a readable video stream"] },
      { id: "codecs", title: "Codecs and metadata", entries: [
        { title: "Video codecs", body: "The container must be readable by the configured FFmpeg/ffprobe runtime. H.264 is the recommended source codec." },
        { title: "Audio codecs", body: "Compatible AAC audio can be carried through; other supported audio may be transcoded to AAC." },
        { title: "Variable frame rate", body: "Metadata is normalized through ffprobe. Review the preview carefully because output timing follows the processing pipeline." },
        { title: "Rotation metadata", body: "Rotation and dimensions are read from the source metadata. Verify orientation in the project preview before masking." },
      ] },
      { id: "recommended", title: "Recommended upload settings", bullets: ["MP4 container", "H.264 video", "AAC audio", "Constant or well-formed frame rate at 60 fps or below", "1080p or below", "A descriptive filename without special control characters"] },
      { id: "errors", title: "Common upload errors", entries: [
        { title: "Unsupported format", body: "The extension, MIME declaration, or detected container is outside the allowlist." },
        { title: "File too large", body: "The file exceeds the active plan or platform upload cap." },
        { title: "Duration, resolution, or FPS too high", body: "The probed media metadata exceeds a configured limit." },
        { title: "Metadata error", body: "The runtime could not read a usable video stream or the file is damaged." },
      ] },
      { id: "output", title: "Output format", body: "Completed jobs are written as MP4 with H.264 video in yuv420p and AAC audio. Aspect ratio and frame rate are preserved where the processing path allows." },
    ],
    cta: { label: "Upload a supported video", href: "/signup", title: "Have an MP4, MOV, or WebM ready?", body: "Create an account and let the uploader validate the actual file." },
  },
  {
    slug: ["faq"], title: "ClearFrame FAQ", description: "Answers about detection, masking, moving overlays, processing quality, billing, credits, storage, privacy, authorized use, and troubleshooting.",
    eyebrow: "Frequently asked questions", heading: "Clear answers before you upload.",
    intro: "The important questions are about what the product can do, what still needs review, what a job costs, and what happens to the file afterward.", kind: "faq",
    sections: [
      { id: "product", title: "Product", entries: [
        { title: "What can ClearFrame remove?", body: "ClearFrame is designed for logos, timestamps, custom subtitles, and visual overlays on footage you own or are authorized to modify. Quality depends on movement, transparency, background detail, and the selected mask." },
        { title: "Will every result be perfect?", body: "No. Hidden texture must be reconstructed, and complex motion or detailed backgrounds can expose artifacts. Generate a preview and adjust the mask before full processing." },
      ] },
      { id: "detection-masking", title: "Detection and masking", entries: [
        { title: "Can I edit the mask manually?", body: "Yes. Use Rectangle, Polygon, Brush, and Eraser tools, then adjust expansion and feathering." },
        { title: "Does it work with moving overlays?", body: "Motion-aware propagation is available only where the tracking path supports it. The current MVP persists a full-video static mask, so moving regions may require manual correction or may not suit the current processing path." },
      ] },
      { id: "processing", title: "Processing and quality", entries: [
        { title: "Is audio preserved?", body: "Compatible audio is preserved where technically possible. Other supported audio may be transcoded to AAC for the final MP4." },
        { title: "Which formats are supported?", body: "The current allowlist is MP4, MOV, and WebM, subject to codec and metadata validation." },
      ] },
      { id: "billing", title: "Billing and credits", entries: [
        { title: "How are credits calculated?", body: "The current backend charges 100 credits for a processing job. Daily allowances come from the active Plan API and reset on the scheduled daily cycle." },
        { title: "What happens if a job fails?", body: "The failure path records a refund transaction and returns the job cost when processing does not complete, capped by the plan's daily allowance." },
        { title: "How do I cancel a subscription?", body: "Use Billing in your account. Cancellation is sent through the payment service and the resulting plan state is shown in the account." },
      ] },
      { id: "files-privacy", title: "Files and privacy", entries: [
        { title: "How long are files stored?", body: "Default retention is 24 hours for originals and previews, 6 hours for failed artifacts, and 7 days for outputs. Plan or administrator settings may change applicable windows." },
        { title: "Can administrators access videos?", body: "Administrative access is permission-controlled and should be used only for authorized support, compliance, or operations. Sensitive actions are designed to be auditable." },
      ] },
      { id: "authorized-use", title: "Authorized use", entries: [
        { title: "Can ClearFrame remove any watermark?", body: "No. Do not use ClearFrame for third-party ownership marks, stock previews, required attribution, DRM, or content you are not authorized to edit." },
      ] },
      { id: "troubleshooting", title: "Troubleshooting", entries: [
        { title: "Why did upload validation fail?", body: "The container, MIME type, file size, duration, dimensions, frame rate, or video stream may be outside the active limits. The uploader returns the specific failing check." },
        { title: "What if detection finds nothing?", body: "Retry the analysis or switch to manual masking. An empty detection result does not block the editor." },
      ] },
    ],
    cta: { label: "Visit the Help Center", href: "/support", title: "Need help with a real project?", body: "Use the Help Center for account, billing, format, and contact routes." },
  },
  {
    slug: ["changelog"], title: "ClearFrame Changelog", description: "A concise, maintainable record of verified ClearFrame improvements across marketing, masking, billing, administration, processing, and security.",
    eyebrow: "Product updates", heading: "Verified changes, without a fabricated backstory.",
    intro: "This changelog contains only work represented in the current project. Add future entries to the same data structure with a date, area, status, and supporting route.", kind: "changelog",
    sections: [
      { id: "2026-07-marketing", title: "July 2026", entries: [
        { title: "Complete public product and resource pages", body: "Expanded navigation destinations with product-specific workflows, limitations, metadata, and responsive visuals.", status: "Shipped" },
        { title: "Accessible marketing navigation", body: "Improved mega-menu descriptions, mobile navigation, keyboard focus, and consistent destinations.", status: "Shipped" },
      ] },
      { id: "2026-07-editor", title: "July 2026 · Editor", entries: [
        { title: "Mask workspace controls", body: "Added Rectangle, Polygon, Brush, Eraser, expansion, feathering, temporal smoothing, undo, reset, and detection review states.", status: "Shipped" },
        { title: "Preview and processing review", body: "Added preview generation, comparison controls, queue status, failed-job handling, and signed output downloads.", status: "Shipped" },
      ] },
      { id: "2026-07-operations", title: "July 2026 · Operations", entries: [
        { title: "Plan and credit administration", body: "Added live public plan data, credit ledgers, failed-job refunds, subscriptions, promo validation, and Razorpay billing paths.", status: "Shipped" },
        { title: "Compliance and retention operations", body: "Added ownership confirmation records, abuse review, project restrictions, cleanup windows, and administrative audit controls.", status: "Shipped" },
      ] },
    ],
    cta: { label: "Explore the product", href: "/product", title: "See where these updates live.", body: "Open the product overview for the complete workflow." },
  },
  {
    slug: ["about"], title: "About ClearFrame", description: "Learn ClearFrame's review-first video cleanup mission, responsible-use boundary, privacy principles, and current product stage.",
    eyebrow: "About ClearFrame", heading: "Automation should accelerate editing without hiding the important decisions.",
    intro: "ClearFrame combines detection, precise masking, preview review, managed processing, and responsible-use controls for footage the user has the right to modify.", kind: "about",
    sections: [
      { id: "mission", title: "The product mission", body: "Make legitimate video cleanup easier to review, easier to correct, and easier to understand from upload through deletion." },
      { id: "philosophy", title: "Review-first editing", entries: [
        { title: "Automation proposes", body: "Detection narrows the search and processing handles repetitive frame work." },
        { title: "The editor confirms", body: "The user owns the authorization decision, the selected region, the preview review, and the full-job approval." },
      ] },
      { id: "responsible-use", title: "Responsible use", body: "The platform is not for DRM removal, stock-preview watermarks, required attribution, or third-party ownership marks. Authorization is part of the product flow rather than a hidden policy footnote." },
      { id: "privacy-processing", title: "Privacy and processing principles", bullets: ["Authenticated project access", "Private storage paths", "Temporary signed downloads", "Configured artifact cleanup", "No training on uploaded media without explicit opt-in", "Auditable administrative controls"] },
      { id: "stage", title: "Current product stage", body: "ClearFrame is an active MVP with a complete account, upload, detection, masking, preview, queued processing, export, billing, and administrative foundation. Some motion tracking and team-workspace capabilities remain limited or planned." },
    ],
    cta: { label: "See how it works", href: "/how-it-works", title: "Follow the product from upload to output.", body: "The workflow guide shows every visible approval point." },
  },
  {
    slug: ["terms"], title: "ClearFrame Terms of Service", description: "Terms governing ClearFrame accounts, authorized content, processing, billing, prohibited use, service availability, and account enforcement.",
    eyebrow: "Legal", heading: "Terms of Service.", intro: "These terms describe the conditions for using ClearFrame. They are written as a practical product agreement and should be reviewed with the Acceptable Use and Privacy policies.", kind: "legal", lastUpdated: "July 21, 2026",
    sections: [
      { id: "agreement", title: "1. Agreement and eligibility", body: "By creating an account or using ClearFrame, you agree to these terms and confirm that you can enter this agreement. If you use the service for an organization, you represent that you are authorized to bind it." },
      { id: "accounts", title: "2. Accounts", body: "Provide accurate registration information, protect your credentials, and notify support of suspected unauthorized access. You are responsible for activity performed through your account unless caused by a ClearFrame security failure." },
      { id: "content", title: "3. Content authorization", body: "You retain rights in your uploaded media and represent that you own it or have sufficient permission to upload, modify, and process it. Do not submit material when a license, contract, law, or rights holder prohibits the intended edit." },
      { id: "acceptable-use", title: "4. Acceptable use", body: "You may not use ClearFrame to remove third-party ownership marks, paid stock previews, required attribution, DRM, access controls, or technical protection measures. Fraud, impersonation, privacy violations, abuse, and unlawful content are also prohibited." },
      { id: "processing", title: "5. Processing and results", body: "Results vary with the source, mask, motion, texture, and selected preset. You are responsible for reviewing previews and completed outputs before publication or delivery." },
      { id: "billing", title: "6. Plans, credits, and billing", body: "Plan prices, billing intervals, credits, and limits are shown before checkout. Paid subscriptions use Razorpay where configured. Promotional eligibility and final prices are validated by the server. Cancellation and renewal status appear in your account." },
      { id: "availability", title: "7. Availability and changes", body: "Features, limits, retention, and processing availability may change for security, legal, operational, or product reasons. Material changes will be reflected in the product or policy pages." },
      { id: "enforcement", title: "8. Suspension and termination", body: "ClearFrame may restrict a project or account to prevent abuse, comply with law, protect rights holders, or secure the service. You may request account deletion through the account controls, subject to legal holds and required records." },
      { id: "contact", title: "9. Contact", body: "Questions about these terms can be sent to support@clearframe.app or through the Contact page." },
    ],
    cta: { label: "Contact support", href: "/contact", title: "Have a question about these terms?", body: "Choose General support or Compliance report on the contact form." },
  },
  {
    slug: ["privacy"], title: "ClearFrame Privacy Policy", description: "How ClearFrame handles account data, uploaded media, project metadata, billing records, security logs, retention, deletion, and privacy requests.",
    eyebrow: "Privacy", heading: "Privacy Policy.", intro: "This policy explains what ClearFrame processes to provide accounts, edit authorized footage, operate billing, prevent abuse, and maintain the service.", kind: "legal", lastUpdated: "July 21, 2026",
    sections: [
      { id: "collected", title: "1. Information we process", body: "Account details, authentication records, subscription and payment references, project metadata, uploaded media, masks, previews, outputs, support messages, authorization confirmations, and security or audit logs." },
      { id: "use", title: "2. How information is used", body: "To authenticate users, validate uploads, process videos, provide previews and downloads, manage plans and credits, troubleshoot failures, prevent abuse, enforce policy, and improve reliability." },
      { id: "media", title: "3. Uploaded media", body: "Media is used to perform the requested project workflow. ClearFrame does not train models on uploaded videos without explicit opt-in. Do not submit more personal or confidential information than the edit requires." },
      { id: "sharing", title: "4. Service providers and disclosure", body: "Infrastructure, storage, and payment providers may process limited data needed to deliver their service. Information may also be disclosed when legally required or necessary to investigate abuse and protect users or rights holders." },
      { id: "security", title: "5. Security", body: "The product uses authenticated access, token controls, password hashing, role checks, controlled storage paths, signed downloads, secret handling, and audit records. No security control eliminates all risk." },
      { id: "retention", title: "6. Retention and deletion", body: "Default artifact windows are 24 hours for originals and previews, 6 hours for failed artifacts, and 7 days for outputs, unless a plan, administrator setting, legal hold, or operational requirement changes the applicable period." },
      { id: "rights", title: "7. Requests and choices", body: "Use account controls or contact support to request access, correction, export, or deletion where applicable. Some billing, security, audit, and compliance records may be retained when law or legitimate operational needs require it." },
      { id: "contact", title: "8. Contact", body: "Send privacy questions to support@clearframe.app through the Contact page and select the most relevant category." },
    ],
    cta: { label: "Contact us about privacy", href: "/contact", title: "Need to make a privacy request?", body: "Include the account email and a clear description, but do not attach sensitive footage to the first message." },
  },
  {
    slug: ["acceptable-use"], title: "ClearFrame Acceptable Use Policy", description: "Permitted and prohibited uses of ClearFrame, including ownership-mark removal, DRM, unlawful content, reporting, and enforcement.",
    eyebrow: "Legal", heading: "Acceptable Use Policy.", intro: "This policy protects creators, rights holders, customers, and the platform by defining the boundary for video processing in direct language.", kind: "legal", lastUpdated: "July 21, 2026",
    sections: [
      { id: "permitted", title: "1. Permitted use", body: "Process footage you created, own, licensed for modification, or have explicit permission to edit. Examples include your own logo, your own timestamp, client-approved branding, licensed archives, and public-domain material." },
      { id: "ownership-marks", title: "2. Prohibited ownership-mark removal", body: "Do not remove a watermark, logo, attribution, or notice that identifies a third-party rights holder or that a license requires you to preserve." },
      { id: "circumvention", title: "3. No circumvention", body: "Do not use ClearFrame to bypass DRM, access controls, paid stock previews, subscription gates, or other technical protection measures." },
      { id: "harm", title: "4. Unlawful or harmful use", body: "Do not use the service for fraud, impersonation, deceptive provenance, privacy violations, harassment, exploitation, or activity prohibited by applicable law." },
      { id: "reporting", title: "5. Reporting", body: "Use the Compliance report category on the Contact page. Include the relevant project or job reference when available and avoid sharing unrelated personal data." },
      { id: "enforcement", title: "6. Enforcement", body: "ClearFrame may block a job, restrict downloads, preserve relevant audit records, place a legal hold, suspend an account, or cooperate with lawful requests when a credible violation is identified." },
      { id: "appeal", title: "7. Questions and review", body: "If you believe an action was taken in error, contact support with the account and project reference and explain the authorization basis." },
    ],
    cta: { label: "Read the authorized-use guide", href: "/authorized-use", title: "Prefer examples to policy clauses?", body: "The authorized-use guide compares allowed and prohibited projects visually." },
  },
  {
    slug: ["security"], title: "ClearFrame Security", description: "Security practices across authentication, video upload, private storage, signed URLs, role-based access, processing isolation, audit logging, cleanup, and disclosure.",
    eyebrow: "Security", heading: "Security across upload, processing, and delivery.", intro: "ClearFrame applies layered controls to accounts, projects, media, workers, administrative actions, and completed outputs without claiming certifications the product has not obtained.", kind: "legal", lastUpdated: "July 21, 2026",
    sections: [
      { id: "transport", title: "1. Transport and secrets", body: "Production traffic should use HTTPS. Application secrets, payment credentials, token keys, and storage credentials stay in protected environment configuration and are not exposed in the frontend." },
      { id: "accounts", title: "2. Account security", body: "Passwords are hashed, access and refresh tokens expire, account status is checked, and sensitive routes require authenticated ownership or administrative permissions." },
      { id: "storage", title: "3. Media storage and delivery", body: "Media uses private storage paths, validated filenames, MIME and container checks, authenticated project access, and temporary signed download links." },
      { id: "processing", title: "4. Processing isolation", body: "Queued jobs use explicit task states, dedicated processing paths, timeouts, retries, and controlled FFmpeg argument lists. User filenames are never concatenated into shell commands." },
      { id: "access", title: "5. Role-based administration", body: "Administrative routes verify permissions server-side. Sensitive support, billing, compliance, retention, and secret operations are separated by role." },
      { id: "audit", title: "6. Audit and monitoring", body: "Important administrative actions, credit transactions, authorization confirmations, project state changes, and compliance operations are designed to leave traceable records." },
      { id: "cleanup", title: "7. Automatic cleanup", body: "Originals, previews, failures, and outputs follow configured retention windows. Legal holds and compliance restrictions can pause normal cleanup when required." },
      { id: "disclosure", title: "8. Responsible disclosure", body: "Use the Security report category on the Contact page. Share clear reproduction steps, avoid unnecessary personal data, and do not access or modify another user's content." },
      { id: "certifications", title: "9. Certifications", body: "ClearFrame does not claim SOC 2, ISO 27001, HIPAA, GDPR certification, or another external certification on this page." },
    ],
    cta: { label: "Report a security issue", href: "/contact", title: "Found a vulnerability?", body: "Use responsible disclosure and avoid attaching sensitive footage to the first message." },
  },
  {
    slug: ["status"], title: "ClearFrame Service Status", description: "Understand the ClearFrame service areas that affect web access, API authentication, storage, queue processing, and export.",
    eyebrow: "Service status", heading: "The workflow depends on more than the website.", intro: "A healthy web page does not prove that storage, the database, the queue, or workers are available. Live operational diagnosis uses the authenticated administration tools.", kind: "status",
    sections: [
      { id: "web", title: "Web application", body: "Navigation, account pages, dashboard, editor, preview review, and result views." },
      { id: "api", title: "API and authentication", body: "Account, project, upload, billing, and authorization requests." },
      { id: "storage", title: "Upload and storage", body: "Signed or controlled upload paths, project artifacts, previews, and outputs." },
      { id: "processing", title: "Queue and processing workers", body: "Detection, inpainting, encoding, retries, and progress updates." },
    ],
    cta: { label: "Contact support", href: "/contact", title: "A project is not progressing?", body: "Include the project or job reference so support can identify the affected service area." },
  },
];

export const seoPageByPath = new Map(seoPages.map((page) => [page.slug.join("/"), page]));
