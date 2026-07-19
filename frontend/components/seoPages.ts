export type SeoSection = { title: string; body: string; bullets?: string[] };
export type SeoPage = {
  slug: string[];
  title: string;
  description: string;
  eyebrow: string;
  heading: string;
  intro: string;
  sections: SeoSection[];
};

export const seoPages: SeoPage[] = [
  { slug: ["how-it-works"], title: "How ClearFrame Works", description: "Learn how ClearFrame detects, masks, previews, and exports authorized video cleanup projects.", eyebrow: "Workflow", heading: "From authorized footage to reviewed export.", intro: "ClearFrame combines AI-assisted detection with precise manual controls so every important decision stays visible.", sections: [
    { title: "1. Upload authorized footage", body: "Upload an MP4, MOV, or WebM file that you own or are licensed to modify.", bullets: ["Ownership confirmation", "Secure upload validation", "Original media properties recorded"] },
    { title: "2. Detect or draw a mask", body: "Review suggested overlay regions or define the exact area manually.", bullets: ["Confidence-ranked detection", "Frame-accurate masking", "Motion-aware tracking"] },
    { title: "3. Preview and approve", body: "Compare a short preview before committing to the complete render.", bullets: ["Before-and-after review", "Mask refinement", "Explicit approval gate"] },
    { title: "4. Export the result", body: "Process the approved project and download the completed file through a controlled link.", bullets: ["Original audio preserved where technically possible", "Resolution and frame rate retained", "Controlled download access"] },
  ] },
  { slug: ["solutions", "content-creators"], title: "Video Cleanup for Content Creators", description: "A reviewable video cleanup workflow for creators editing footage they own.", eyebrow: "For content creators", heading: "Polish your own footage without losing creative control.", intro: "Remove distracting overlays from authorized footage while keeping every mask, preview, and export decision in your hands.", sections: [
    { title: "Move quickly on repeat edits", body: "Use assisted detection to identify common logos, timestamps, subtitles, and overlays." },
    { title: "Keep the final say", body: "Review every suggested region and refine masks before full processing begins." },
    { title: "Preserve the source experience", body: "Maintain original audio and core video properties wherever technically possible." },
  ] },
  { slug: ["solutions", "video-editors"], title: "Video Cleanup for Professional Editors", description: "Frame-accurate overlay cleanup tools for professional video editors working on authorized footage.", eyebrow: "For video editors", heading: "Precision controls for demanding cleanup work.", intro: "Combine automated region proposals with manual, frame-level control for client footage you are authorized to edit.", sections: [
    { title: "Start with a useful proposal", body: "AI detection surfaces likely regions so you can focus attention where it matters." },
    { title: "Refine across motion and cuts", body: "Adjust masks and tracking when subjects move or scenes change." },
    { title: "Approve before the long render", body: "Use short previews to validate the result before processing the complete file." },
  ] },
  { slug: ["solutions", "agencies"], title: "Authorized Video Cleanup for Agencies", description: "A controlled video cleanup workflow for agencies and teams handling licensed client footage.", eyebrow: "For agencies and teams", heading: "A clear review path for client footage.", intro: "Keep authorization, preview approval, and output handling visible throughout every cleanup project.", sections: [
    { title: "Document the authorization boundary", body: "Only submit footage your team owns or has permission to modify." },
    { title: "Standardize review", body: "Use the same detect, mask, preview, approve, and export sequence across projects." },
    { title: "Control completed outputs", body: "Deliver processed files through managed downloads and configured retention policies." },
  ] },
  { slug: ["authorized-use"], title: "Authorized Use and Video Cleanup Compliance", description: "Understand ClearFrame ownership requirements, acceptable use boundaries, and safeguards for authorized video editing.", eyebrow: "Authorized use", heading: "Built for footage you have the right to edit.", intro: "ClearFrame supports legitimate cleanup work on videos you own or are licensed to modify. It is not intended to defeat ownership controls or access restrictions.", sections: [
    { title: "Permitted projects", body: "Use ClearFrame for your original footage, client footage covered by your agreement, or licensed assets that explicitly permit modification." },
    { title: "Prohibited projects", body: "Do not remove third-party ownership marks, paid stock previews, DRM, access controls, or attribution required by a license." },
    { title: "Workflow safeguards", body: "Ownership confirmation, preview review, controlled downloads, and retention settings help keep the authorization boundary visible." },
  ] },
  { slug: ["supported-formats"], title: "Supported Video Formats and Upload Requirements", description: "Review ClearFrame support for MP4, MOV, WebM, audio preservation, resolution, and upload validation.", eyebrow: "Video compatibility", heading: "Formats designed for practical editing workflows.", intro: "ClearFrame validates each upload before processing and preserves essential media properties where technically possible.", sections: [
    { title: "Supported containers", body: "Upload MP4, MOV, and WebM video files." },
    { title: "Media preservation", body: "The workflow is designed to retain original audio, aspect ratio, duration, frame rate, and resolution where the selected processing method allows." },
    { title: "Upload validation", body: "File size, duration, dimensions, frame rate, and codec compatibility are checked before a project enters processing." },
  ] },
  { slug: ["faq"], title: "ClearFrame Frequently Asked Questions", description: "Answers about authorized video cleanup, supported formats, processing, quality, retention, and account plans.", eyebrow: "Frequently asked questions", heading: "Clear answers before you begin.", intro: "Learn what ClearFrame processes, how review works, and which authorization rules apply.", sections: [
    { title: "Can I process any video?", body: "No. You must own the footage or have a license or agreement that allows you to modify it." },
    { title: "Does ClearFrame remove DRM?", body: "No. ClearFrame does not remove DRM, access controls, or other technical protection measures." },
    { title: "Can I review the result first?", body: "Yes. The workflow provides a short preview so you can inspect and refine the mask before approving the full render." },
    { title: "What happens to original audio?", body: "Original audio is preserved where technically possible and remuxed into the completed output." },
    { title: "How long are files retained?", body: "Retention depends on the active platform policy and plan. Administrators can configure retention windows for originals, previews, failures, and outputs." },
  ] },
  { slug: ["changelog"], title: "ClearFrame Product Changelog", description: "Track improvements to ClearFrame detection, masking, preview, processing, security, and video export workflows.", eyebrow: "Product updates", heading: "What has changed in ClearFrame.", intro: "A concise record of meaningful product and platform improvements.", sections: [
    { title: "July 2026 — Marketing and navigation", body: "Introduced crawlable public pages, unique metadata, corrected cross-page navigation, and expanded accessibility behavior." },
    { title: "Processing workflow", body: "Added review-before-export controls, progress reporting, and controlled output downloads." },
    { title: "Detection and masking", body: "Improved candidate ranking, manual region controls, temporal tracking, and preview rendering." },
  ] },
  { slug: ["about"], title: "About ClearFrame", description: "Learn why ClearFrame was built and how it approaches authorized, reviewable video cleanup.", eyebrow: "About ClearFrame", heading: "Video cleanup with the important decisions left visible.", intro: "ClearFrame is built around a simple principle: automation should accelerate legitimate editing work without hiding authorization or review decisions.", sections: [
    { title: "Our approach", body: "AI proposes useful regions, editors refine them, and a preview confirms the result before the complete render." },
    { title: "Our boundary", body: "The product is for footage users own or are licensed to modify. DRM removal and unauthorized ownership-mark removal are outside the product scope." },
    { title: "Our focus", body: "We prioritize transparent controls, predictable processing, media preservation, and secure output handling." },
  ] },
  { slug: ["contact"], title: "Contact ClearFrame", description: "Contact ClearFrame about product support, security, authorized workflows, or business inquiries.", eyebrow: "Contact", heading: "Talk with the ClearFrame team.", intro: "Choose the address that best matches your request so it reaches the right workflow.", sections: [
    { title: "Product support", body: "For account and project assistance, use the support channel available from your account." },
    { title: "Security reports", body: "Report potential vulnerabilities through the dedicated security contact channel. Do not include sensitive footage in the first message." },
    { title: "Business inquiries", body: "Use the business inquiry channel to discuss agency or team requirements." },
  ] },
  { slug: ["terms"], title: "ClearFrame Terms of Service", description: "Read the terms governing ClearFrame accounts, authorized video processing, acceptable use, and service access.", eyebrow: "Legal", heading: "Terms of Service.", intro: "These terms describe the conditions for using ClearFrame and form part of the agreement between ClearFrame and each account holder.", sections: [
    { title: "Account responsibility", body: "You are responsible for accurate account information, credential security, and all activity performed through your account." },
    { title: "Content authorization", body: "You represent that you own or have sufficient permission to upload, modify, and process every submitted file." },
    { title: "Prohibited use", body: "You may not use the service to remove required ownership marks, paid stock previews, DRM, access controls, or legally required attribution." },
    { title: "Service operation", body: "Processing availability, limits, retention, and features may vary by plan and operational conditions." },
    { title: "Account enforcement", body: "Accounts may be limited or suspended when activity violates these terms, applicable law, or platform safety controls." },
  ] },
  { slug: ["privacy"], title: "ClearFrame Privacy Policy", description: "Learn how ClearFrame handles account information, uploaded videos, processing data, retention, and security.", eyebrow: "Privacy", heading: "Privacy Policy.", intro: "This policy explains the information ClearFrame uses to provide accounts, process authorized footage, secure the service, and operate support.", sections: [
    { title: "Information collected", body: "We process account details, project metadata, uploaded media, generated previews and outputs, usage records, and security logs." },
    { title: "How information is used", body: "Information is used to provide processing, maintain accounts, prevent abuse, troubleshoot failures, and improve service reliability." },
    { title: "Media retention", body: "Originals, previews, failed artifacts, and completed outputs follow configured retention windows and may be removed automatically." },
    { title: "Data security", body: "Access controls, controlled downloads, and operational safeguards are used to reduce unauthorized access." },
    { title: "Privacy requests", body: "Submit access, correction, or deletion requests through the privacy contact channel, subject to applicable requirements." },
  ] },
  { slug: ["acceptable-use"], title: "ClearFrame Acceptable Use Policy", description: "Review permitted and prohibited uses of ClearFrame video cleanup and processing tools.", eyebrow: "Acceptable use", heading: "Use ClearFrame only for authorized editing.", intro: "This policy protects creators, rights holders, customers, and the platform by defining the permitted boundary for video processing.", sections: [
    { title: "Permitted use", body: "Process footage you created, own, or have explicit permission to modify." },
    { title: "Prohibited ownership-mark removal", body: "Do not remove watermarks or attribution that identify a third-party rights holder or that a license requires you to preserve." },
    { title: "No circumvention", body: "Do not bypass DRM, access controls, paid previews, or technical protection measures." },
    { title: "No unlawful or harmful use", body: "Do not use the service for fraud, impersonation, privacy violations, abuse, or activity prohibited by law." },
    { title: "Enforcement", body: "ClearFrame may block processing, retain relevant security records, suspend accounts, or cooperate with lawful requests when violations are identified." },
  ] },
  { slug: ["security"], title: "ClearFrame Security", description: "Learn about ClearFrame account security, controlled downloads, processing isolation, retention, and vulnerability reporting.", eyebrow: "Security", heading: "Security across upload, processing, and delivery.", intro: "ClearFrame applies safeguards throughout the media workflow and keeps operational controls visible to administrators.", sections: [
    { title: "Account protection", body: "Authentication, token controls, role checks, and account-status enforcement protect access to projects and administration." },
    { title: "Media handling", body: "Uploads are validated, project access is checked, and completed outputs use controlled download paths." },
    { title: "Operational controls", body: "Administrators can configure limits, retention windows, enabled models, retries, and maintenance mode." },
    { title: "Responsible disclosure", body: "Submit vulnerability reports with clear reproduction steps and no unnecessary personal data." },
  ] },
  { slug: ["status"], title: "ClearFrame Service Status", description: "Check the operational status of ClearFrame web, API, storage, processing, and export services.", eyebrow: "Service status", heading: "ClearFrame systems status.", intro: "Current service health is reported across the core workflow.", sections: [
    { title: "Web application", body: "Operational" },
    { title: "API and authentication", body: "Operational" },
    { title: "Upload and storage", body: "Operational" },
    { title: "Detection, processing, and export", body: "Operational" },
  ] },
];

export const seoPageByPath = new Map(seoPages.map((page) => [page.slug.join("/"), page]));