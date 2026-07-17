import { api } from "./api";
import type {
  AbuseAction,
  AbuseReportSummary,
  ActionResponse,
  AdminJob,
  AdminOverview,
  AdminUser,
  AuditEntry,
  JobAction,
  SystemConfig,
  SystemConfigUpdate,
  UserAction,
  WorkerInfo,
} from "@/types";

/**
 * Phase 8 — admin API wrappers (SRS ADMIN-001..007). Every route sits behind
 * `require_admin` server-side; the client additionally guards the page on
 * `user.role === "admin"` so a non-admin never fetches these.
 */
export const adminApi = {
  // ADMIN-001
  overview: () => api.get<AdminOverview>("/admin/overview").then((r) => r.data),

  // ADMIN-002
  listUsers: (q?: string) =>
    api.get<AdminUser[]>("/admin/users", { params: q ? { q } : {} }).then((r) => r.data),
  actOnUser: (userId: string, action: UserAction) =>
    api.post<ActionResponse>(`/admin/users/${userId}`, { action }).then((r) => r.data),

  // ADMIN-003
  listJobs: (params: { status?: string; user_id?: string; q?: string } = {}) =>
    api.get<AdminJob[]>("/admin/jobs", { params }).then((r) => r.data),
  actOnJob: (jobId: string, action: JobAction) =>
    api.post<ActionResponse>(`/admin/jobs/${jobId}`, { action }).then((r) => r.data),
  deleteJobTemp: (jobId: string) =>
    api.delete<{ deleted: number }>(`/admin/jobs/${jobId}/temp`).then((r) => r.data),

  // ADMIN-004
  listWorkers: () => api.get<WorkerInfo[]>("/admin/workers").then((r) => r.data),

  // ADMIN-005
  getConfig: () => api.get<SystemConfig>("/admin/config").then((r) => r.data),
  updateConfig: (body: SystemConfigUpdate) =>
    api.patch<SystemConfig>("/admin/config", body).then((r) => r.data),

  // ADMIN-006
  listAudit: () => api.get<AuditEntry[]>("/admin/audit").then((r) => r.data),

  // ADMIN-007
  listAbuse: (status?: string) =>
    api.get<AbuseReportSummary[]>("/admin/abuse", { params: status ? { status } : {} }).then((r) => r.data),
  actOnAbuse: (reportId: string, action: AbuseAction) =>
    api.post<ActionResponse>(`/admin/abuse/${reportId}`, { action }).then((r) => r.data),
};
