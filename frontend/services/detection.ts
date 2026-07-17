import { api } from "./api";
import type {
  AnalyzeResponse,
  ApproveCandidateRequest,
  ApproveCandidateResponse,
  CandidateListResponse,
  WatermarkCandidate,
} from "@/types";

/**
 * Phase 7 — AI detection API wrappers (SRS DETECT-001..007).
 *
 * Analyze runs as a Celery job on the `detection` queue. Progress arrives via
 * polling `processApi.getJobStatus` (same SSE namespace as Phase 5 process
 * jobs) — no separate event machinery is needed.
 */
export const detectionApi = {
  /** POST /projects/{id}/analyze — enqueue (or reuse) an analyze job. */
  analyze: (projectId: string, rerun = false) =>
    api
      .post<AnalyzeResponse>(`/projects/${projectId}/analyze`, null, {
        params: { rerun },
      })
      .then((r) => r.data),

  /** GET /projects/{id}/candidates — ranked candidates + manual-fallback flag. */
  listCandidates: (projectId: string) =>
    api
      .get<CandidateListResponse>(`/projects/${projectId}/candidates`)
      .then((r) => r.data),

  /** GET /candidates/{id} — single candidate detail. */
  getCandidate: (candidateId: string) =>
    api
      .get<WatermarkCandidate>(`/candidates/${candidateId}`)
      .then((r) => r.data),

  /** POST /candidates/{id}/approve — promote a candidate to a WatermarkMask. */
  approve: (candidateId: string, body?: ApproveCandidateRequest) =>
    api
      .post<ApproveCandidateResponse>(`/candidates/${candidateId}/approve`, body ?? {})
      .then((r) => r.data),
};