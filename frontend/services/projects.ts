import { api } from "./api";
import type { ComplianceConfirmation, VideoProject } from "@/types";

export type ProjectListQuery = {
  status?: string;
  q?: string;
};

export const projectsApi = {
  list: (query: ProjectListQuery = {}) =>
    api
      .get<VideoProject[]>("/projects", { params: query })
      .then((r) => r.data),
  get: (id: string) =>
    api.get<VideoProject>(`/projects/${id}`).then((r) => r.data),
  create: (body: { title?: string; filename: string; total_bytes?: number }) =>
    api.post<VideoProject>("/projects", body).then((r) => r.data),
  confirmCompliance: (
    id: string,
    body: { ownership_confirmed: boolean; policy_version?: string },
  ) =>
    api
      .post<ComplianceConfirmation>(`/projects/${id}/compliance`, {
        ownership_confirmed: body.ownership_confirmed,
        policy_version: body.policy_version ?? "1.0",
      })
      .then((r) => r.data),

  // FR-15 history actions (Phase 6). delete + duplicate-settings are spec'd
  // but the live DELETE /projects/{id} & duplicate endpoints land in Phase 8
  // (admin hardening). retry/download wire to Phase 5/6 endpoints.
  delete: (id: string) =>
    // 404 stubs are caught + thrown upstream — admin endpoints land later.
    api.delete<void>(`/projects/${id}`).then((r) => r.data) as unknown as Promise<void>,
  duplicate: (id: string) =>
    api.post<VideoProject>("/projects/" + id + "/duplicate").then((r) => r.data),
  duplicateSettings: (id: string) =>
    api.post<VideoProject>("/projects/" + id + "/duplicate").then((r) => r.data),
};

