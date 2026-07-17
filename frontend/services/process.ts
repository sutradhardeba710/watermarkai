import { api } from "./api";
import type {
  JobStatus,
  ProcessResponse,
  PreviewRequest,
  PreviewResponse,
  DownloadUrlResponse,
} from "@/types";

/**
 * Phase 5 + 6 — processing + preview/download API wrappers.
 *
 * Progress arrives via polling `getJobStatus` rather than the SSE stream so the
 * browser can keep the bearer token in the standard axios Authorization header
 * (EventSource cannot set custom headers portably across browsers).
 */
export const processApi = {
  start: (projectId: string, body?: { settings?: { quality_mode?: "fast" | "balanced" | "high"; mask_expansion?: number; mask_feathering?: number; temporal_smoothing?: boolean; preserve_audio?: boolean } }) =>
    api.post<ProcessResponse>(`/projects/${projectId}/process`, body ?? {}).then((r) => r.data),

  getJobStatus: (jobId: string) =>
    api.get<JobStatus>(`/jobs/${jobId}/status`).then((r) => r.data),

  listProjectJobs: (projectId: string) =>
    api.get<JobStatus[]>(`/projects/${projectId}/jobs`).then((r) => r.data),
};

export const previewApi = {
  create: (projectId: string, body?: PreviewRequest) =>
    api.post<PreviewResponse>(`/projects/${projectId}/preview`, body ?? {}).then((r) => r.data),
  get: (projectId: string) =>
    api.get<PreviewResponse>(`/projects/${projectId}/preview`).then((r) => r.data),
  clipUrl: (projectId: string) =>
    `${api.defaults.baseURL}/projects/${projectId}/preview-clip`,
};

export const downloadApi = {
  issueUrl: (projectId: string, expires_seconds = 1800) =>
    api
      .post<DownloadUrlResponse>(`/projects/${projectId}/download-url`, { expires_seconds })
      .then((r) => r.data),
  /**
   * Returns a same-origin URL the browser can hit directly. The signed token is
   * passed as a query param; the backend `/projects/{id}/output?token=...` route
   * validates it and streams the MP4. We also pass the bearer so the route's
   * `get_current_user` dependency is satisfied.
   */
  streamUrl: (projectId: string, token: string) =>
    `${api.defaults.baseURL}/projects/${projectId}/output?token=${encodeURIComponent(token)}`,
};

/** Polls job status until terminal or `maxAttempts`. */
export async function pollJob(
  jobId: string,
  onUpdate: (s: JobStatus) => void,
  opts: { intervalMs?: number; maxAttempts?: number; signal?: AbortSignal } = {},
): Promise<JobStatus> {
  const intervalMs = opts.intervalMs ?? 1500;
  const maxAttempts = opts.maxAttempts ?? 800; // ~20 min default
  for (let i = 0; i < maxAttempts; i++) {
    if (opts.signal?.aborted) throw new DOMException("Aborted", "AbortError");
    const s = await processApi.getJobStatus(jobId);
    onUpdate(s);
    if (["completed", "failed", "cancelled", "expired"].includes(s.status)) return s;
    await new Promise((res) => setTimeout(res, intervalMs));
  }
  throw new Error("Job polling timed out.");
}
