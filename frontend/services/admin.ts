import { api } from "./api";
import type {
  AbuseAction,
  AbuseReportSummary,
  AbuseReportDetail,
  AbuseSeverity,
  ActionResponse,
  AdminJob,
  AdminJobDetail,
  AdminMe,
  AdminOverview,
  AdminPlan,
  AdminProject,
  AdminProjectAction,
  AdminProjectDetail,
  AdminPromo,
  AdminSession,
  AdminSubscriptionListItem,
  AdminUser,
  AdminUserAction,
  AdminUserDetail,
  AuditEntry,
  BillingOverview,
  CreditDashboard,
  CreditTransaction,
  ComplianceAction,
  ComplianceOverview,
  AIModel,
  ModelAction,
  ModelType,
  Preset,
  FeatureFlag,
  NotificationTemplate,
  TemplatePreview,
  BroadcastKind,
  BroadcastTarget,
  BroadcastResponse,
  MaintenanceState,
  JobAction,
  Page,
  Payment,
  PaymentDetail,
  PaymentListItem,
  QueueMetrics,
  Refund,
  RetentionItem,
  StorageAction,
  StorageActionResponse,
  StorageOverview,
  SubscriptionAction,
  SupportNote,
  SystemConfig,
  SystemConfigUpdate,
  WebhookEvent,
  WorkerDetail,
  WorkerInfo,
  Analytics,
  ExportDataset,
  ExportFormat,
  SystemHealth,
  Incident,
  IncidentAction,
  IncidentSeverity,
  AdminListItem,
  AdminMgmtAction,
  GlobalSearch,
  SecretDescriptor,
} from "@/types";

/**
 * Admin API wrappers (SRS ADMIN-001..007 + Admin Panel PRD Phases 1+2).
 * Every route sits behind `require_permission` server-side; the client
 * additionally hides nav/actions via features/admin/permissions.ts, but that
 * is cosmetic — the server is the authority.
 */
export const adminApi = {
  me: () => api.get<AdminMe>("/admin/me").then((r) => r.data),

  // ADMIN-001
  overview: () => api.get<AdminOverview>("/admin/overview").then((r) => r.data),

  // ADMIN-002 / PRD §8
  listUsers: (params: {
    q?: string; status?: string; role?: string; plan?: string;
    verified?: boolean; page?: number; page_size?: number;
  } = {}) =>
    api.get<Page<AdminUser>>("/admin/users", { params }).then((r) => r.data),
  getUser: (userId: string) =>
    api.get<AdminUserDetail>(`/admin/users/${userId}`).then((r) => r.data),
  listUserTransactions: (userId: string, page = 1) =>
    api.get<Page<CreditTransaction>>(`/admin/users/${userId}/transactions`, { params: { page } }).then((r) => r.data),
  listUserPayments: (userId: string) =>
    api.get<Payment[]>(`/admin/users/${userId}/payments`).then((r) => r.data),
  listUserProjects: (userId: string) =>
    api.get<AdminProject[]>(`/admin/users/${userId}/projects`).then((r) => r.data),
  listUserJobs: (userId: string) =>
    api.get<AdminJob[]>(`/admin/users/${userId}/jobs`).then((r) => r.data),
  listUserSessions: (userId: string) =>
    api.get<AdminSession[]>(`/admin/users/${userId}/sessions`).then((r) => r.data),
  listUserActivity: (userId: string, page = 1) =>
    api.get<Page<AuditEntry>>(`/admin/users/${userId}/activity`, { params: { page } }).then((r) => r.data),
  listUserNotes: (userId: string) =>
    api.get<SupportNote[]>(`/admin/users/${userId}/notes`).then((r) => r.data),
  createUserNote: (userId: string, body: { body: string; project_id?: string; pinned?: boolean }) =>
    api.post<SupportNote>(`/admin/users/${userId}/notes`, body).then((r) => r.data),
  deleteNote: (noteId: string) =>
    api.delete<{ deleted: boolean }>(`/admin/notes/${noteId}`).then((r) => r.data),
  actOnUser: (userId: string, action: AdminUserAction, reason?: string) =>
    api.post<{ id: string; account_status: string }>(`/admin/users/${userId}/actions`, { action, reason }).then((r) => r.data),
  changeUserRole: (userId: string, admin_role: string | null) =>
    api.post<{ id: string; admin_role: string | null }>(`/admin/users/${userId}/role`, { admin_role }).then((r) => r.data),
  changeUserPlan: (userId: string, plan_id: string, reason?: string) =>
    api.post<{ id: string; plan_id: string; credits_remaining: number }>(`/admin/users/${userId}/plan`, { plan_id, reason }).then((r) => r.data),
  adjustUserCredits: (userId: string, body: { amount: number; direction: "credit" | "debit"; reason: string; reference?: string }) =>
    api.post<{ id: string; credits_remaining: number; transaction_id: string }>(`/admin/users/${userId}/credits`, body).then((r) => r.data),

  // PRD §9 projects
  listProjects: (params: {
    q?: string; status?: string; user_id?: string; locked?: boolean;
    include_deleted?: boolean; page?: number; page_size?: number;
  } = {}) =>
    api.get<Page<AdminProject>>("/admin/projects", { params }).then((r) => r.data),
  getProject: (projectId: string) =>
    api.get<AdminProjectDetail>(`/admin/projects/${projectId}`).then((r) => r.data),
  actOnProject: (projectId: string, action: AdminProjectAction, opts: { reason?: string; hours?: number } = {}) =>
    api.post<{ id: string; status: string; locked: boolean; expires_at?: string | null }>(
      `/admin/projects/${projectId}/actions`, { action, ...opts }).then((r) => r.data),
  deleteProject: (projectId: string, reason: string) =>
    api.delete<{ id: string; deleted: boolean; deleted_files: number }>(
      `/admin/projects/${projectId}`, { params: { reason } }).then((r) => r.data),

  // ADMIN-003
  listJobs: (params: { status?: string; user_id?: string; q?: string } = {}) =>
    api.get<AdminJob[]>("/admin/jobs", { params }).then((r) => r.data),
  getJob: (jobId: string) =>
    api.get<AdminJobDetail>(`/admin/jobs/${jobId}`).then((r) => r.data),
  actOnJob: (jobId: string, action: JobAction) =>
    api.post<ActionResponse>(`/admin/jobs/${jobId}`, { action }).then((r) => r.data),
  deleteJobTemp: (jobId: string) =>
    api.delete<{ deleted: number }>(`/admin/jobs/${jobId}/temp`).then((r) => r.data),

  // PRD §11 queues
  getQueues: () => api.get<QueueMetrics>("/admin/queues").then((r) => r.data),

  // ADMIN-004
  listWorkers: () => api.get<WorkerInfo[]>("/admin/workers").then((r) => r.data),
  getWorker: (name: string) =>
    api.get<WorkerDetail>(`/admin/workers/${encodeURIComponent(name)}`).then((r) => r.data),

  // ADMIN-005
  getConfig: () => api.get<SystemConfig>("/admin/config").then((r) => r.data),
  updateConfig: (body: SystemConfigUpdate) =>
    api.patch<SystemConfig>("/admin/config", body).then((r) => r.data),

  // ADMIN-006 / PRD §27
  listAudit: (params: {
    action?: string; actor_id?: string; target_type?: string;
    date_from?: string; date_to?: string; page?: number; page_size?: number;
  } = {}) =>
    api.get<Page<AuditEntry>>("/admin/audit", { params }).then((r) => r.data),

  // ADMIN-007
  listAbuse: (status?: string) =>
    api.get<AbuseReportSummary[]>("/admin/abuse", { params: status ? { status } : {} }).then((r) => r.data),
  actOnAbuse: (reportId: string, action: AbuseAction) =>
    api.post<ActionResponse>(`/admin/abuse/${reportId}`, { action }).then((r) => r.data),

  // --- Phase 4: billing / payments / subscriptions / plans / promos / credits ---
  // PRD §13.1
  billingOverview: () => api.get<BillingOverview>("/admin/billing").then((r) => r.data),

  // PRD §13.3
  listPayments: (params: {
    status?: string; user_id?: string; q?: string; page?: number; page_size?: number;
  } = {}) =>
    api.get<Page<PaymentListItem>>("/admin/payments", { params }).then((r) => r.data),
  getPayment: (paymentId: string) =>
    api.get<PaymentDetail>(`/admin/payments/${paymentId}`).then((r) => r.data),
  refundPayment: (paymentId: string, body: { amount_inr: number; reason: string }) =>
    api.post<Refund>(`/admin/payments/${paymentId}/refund`, body).then((r) => r.data),
  updatePaymentNote: (paymentId: string, body: { internal_note?: string; manual_review?: boolean }) =>
    api.post<PaymentDetail>(`/admin/payments/${paymentId}/note`, body).then((r) => r.data),

  // PRD §13.4 / §26
  listWebhooks: (params: { event_type?: string; payment_id?: string; page?: number; page_size?: number } = {}) =>
    api.get<Page<WebhookEvent>>("/admin/webhooks", { params }).then((r) => r.data),
  getWebhook: (eventId: string) =>
    api.get<WebhookEvent>(`/admin/webhooks/${eventId}`).then((r) => r.data),

  // PRD §14
  listSubscriptions: (params: { status?: string; page?: number; page_size?: number } = {}) =>
    api.get<Page<AdminSubscriptionListItem>>("/admin/subscriptions", { params }).then((r) => r.data),
  actOnSubscription: (subscriptionId: string, body: { action: SubscriptionAction; reason?: string; plan_id?: string }) =>
    api.post<AdminSubscriptionListItem>(`/admin/subscriptions/${subscriptionId}/actions`, body).then((r) => r.data),

  // PRD §15
  listPlans: (includeArchived = true) =>
    api.get<AdminPlan[]>("/admin/plans", { params: { include_archived: includeArchived } }).then((r) => r.data),
  createPlan: (body: Partial<AdminPlan> & { id: string; name: string; price_inr: number; credits_per_day: number }) =>
    api.post<AdminPlan>("/admin/plans", body).then((r) => r.data),
  updatePlan: (planId: string, body: Partial<AdminPlan> & { reason?: string }) =>
    api.patch<AdminPlan>(`/admin/plans/${planId}`, body).then((r) => r.data),

  // PRD §16
  listPromos: (active?: boolean) =>
    api.get<AdminPromo[]>("/admin/promos", { params: active === undefined ? {} : { active } }).then((r) => r.data),
  createPromo: (body: {
    code: string; discount_type: string; discount_value: number;
    description?: string; sandbox_only?: boolean; new_users_only?: boolean;
    max_discount_inr?: number; min_purchase_inr?: number;
    max_total_uses?: number; max_uses_per_user?: number;
    starts_at?: string; ends_at?: string; applicable_plans?: string[]; razorpay_offer_id?: string;
  }) =>
    api.post<AdminPromo>("/admin/promos", body).then((r) => r.data),
  updatePromo: (promoId: string, body: Partial<AdminPromo> & { reason?: string }) =>
    api.patch<AdminPromo>(`/admin/promos/${promoId}`, body).then((r) => r.data),

  // PRD §17.1
  creditDashboard: () => api.get<CreditDashboard>("/admin/credits").then((r) => r.data),

  // --- Phase 5: storage & compliance (PRD §18, §21) ---
  // PRD §18.1
  storageOverview: () => api.get<StorageOverview>("/admin/storage").then((r) => r.data),
  // PRD §18.3
  retentionDashboard: (params: { page?: number; page_size?: number } = {}) =>
    api.get<Page<RetentionItem>>("/admin/storage/retention", { params }).then((r) => r.data),
  // PRD §18.4 — guarded by §18.5 delete-safety server-side
  actOnStorage: (projectId: string, body: { action: StorageAction; reason?: string; hours?: number }) =>
    api.post<StorageActionResponse>(`/admin/projects/${projectId}/storage`, body).then((r) => r.data),

  // PRD §21.1
  complianceOverview: () => api.get<ComplianceOverview>("/admin/compliance").then((r) => r.data),
  // PRD §21.2
  listComplianceReports: (params: {
    status?: string; severity?: string; q?: string; page?: number; page_size?: number;
  } = {}) =>
    api.get<Page<AbuseReportSummary>>("/admin/compliance/reports", { params }).then((r) => r.data),
  // PRD §21.4
  getComplianceReport: (reportId: string) =>
    api.get<AbuseReportDetail>(`/admin/compliance/${reportId}`).then((r) => r.data),
  setReportSeverity: (reportId: string, severity: AbuseSeverity) =>
    api.patch<AbuseReportSummary>(`/admin/compliance/${reportId}`, { severity }).then((r) => r.data),
  // PRD §21.5
  actOnCompliance: (reportId: string, body: { action: ComplianceAction; reason?: string }) =>
    api.post<ActionResponse>(`/admin/compliance/${reportId}/actions`, body).then((r) => r.data),

  // --- Phase 6: models, presets, feature flags, notifications, maintenance ---
  // PRD §19
  listModels: (params: { model_type?: ModelType; status?: string } = {}) =>
    api.get<AIModel[]>("/admin/models", { params }).then((r) => r.data),
  registerModel: (body: {
    name: string; model_type: ModelType; version: string;
    supported_job_types?: string[]; supported_resolutions?: string[];
    min_gpu_memory_mb?: number; avg_speed_fps?: number; quality_score?: number;
    compatible_workers?: string[]; previous_version?: string; release_notes?: string;
  }) =>
    api.post<AIModel>("/admin/models", body).then((r) => r.data),
  updateModel: (modelId: string, body: Partial<AIModel>) =>
    api.patch<AIModel>(`/admin/models/${modelId}`, body).then((r) => r.data),
  actOnModel: (modelId: string, body: { action: ModelAction; reason?: string }) =>
    api.post<AIModel>(`/admin/models/${modelId}/actions`, body).then((r) => r.data),

  // PRD §20
  listPresets: (enabled?: boolean) =>
    api.get<Preset[]>("/admin/presets", { params: enabled === undefined ? {} : { enabled } }).then((r) => r.data),
  createPreset: (body: Partial<Preset> & { name: string }) =>
    api.post<Preset>("/admin/presets", body).then((r) => r.data),
  updatePreset: (presetId: string, body: Partial<Preset>) =>
    api.patch<Preset>(`/admin/presets/${presetId}`, body).then((r) => r.data),
  setDefaultPreset: (presetId: string) =>
    api.post<Preset>(`/admin/presets/${presetId}/set-default`, {}).then((r) => r.data),

  // PRD §26.5
  listFeatureFlags: () => api.get<FeatureFlag[]>("/admin/feature-flags").then((r) => r.data),
  updateFeatureFlag: (key: string, enabled: boolean) =>
    api.patch<FeatureFlag>(`/admin/feature-flags/${key}`, { enabled }).then((r) => r.data),

  // PRD §26.6
  getMaintenance: () => api.get<MaintenanceState>("/admin/maintenance").then((r) => r.data),
  updateMaintenance: (body: MaintenanceState) =>
    api.put<MaintenanceState>("/admin/maintenance", body).then((r) => r.data),

  // PRD §23
  listTemplates: () =>
    api.get<NotificationTemplate[]>("/admin/notifications/templates").then((r) => r.data),
  updateTemplate: (templateId: string, body: Partial<NotificationTemplate>) =>
    api.patch<NotificationTemplate>(`/admin/notifications/templates/${templateId}`, body).then((r) => r.data),
  previewTemplate: (templateId: string, variables: Record<string, string>) =>
    api.post<TemplatePreview>(`/admin/notifications/templates/${templateId}/preview`, { variables }).then((r) => r.data),
  sendBroadcast: (body: { kind: BroadcastKind; title: string; message: string; target?: BroadcastTarget; target_plan?: string }) =>
    api.post<BroadcastResponse>("/admin/notifications/broadcast", body).then((r) => r.data),

  // --- Phase 7 ---

  // PRD §24 analytics & reports
  analytics: (windowDays = 30) =>
    api.get<Analytics>("/admin/analytics", { params: { window_days: windowDays } }).then((r) => r.data),
  // PRD §24.5 exports — returns a Blob for download
  createExport: (dataset: ExportDataset, format: ExportFormat = "csv") =>
    api
      .post("/admin/exports", { dataset, format }, { responseType: "blob" })
      .then((r) => r.data as Blob),

  // PRD §25 system health + incidents
  systemHealth: () => api.get<SystemHealth>("/admin/system-health").then((r) => r.data),
  listIncidents: (status?: string) =>
    api.get<Incident[]>("/admin/incidents", { params: status ? { status } : {} }).then((r) => r.data),
  createIncident: (body: { service: string; title: string; severity?: IncidentSeverity; detail?: string }) =>
    api.post<Incident>("/admin/incidents", body).then((r) => r.data),
  actOnIncident: (incidentId: string, body: { action: IncidentAction; note?: string; minutes?: number }) =>
    api.post<Incident>(`/admin/incidents/${incidentId}/actions`, body).then((r) => r.data),

  // PRD §28 administrator management
  listAdministrators: () =>
    api.get<AdminListItem[]>("/admin/administrators").then((r) => r.data),
  inviteAdministrator: (body: { email: string; full_name: string; admin_role: string }) =>
    api.post<AdminListItem>("/admin/administrators", body).then((r) => r.data),
  actOnAdministrator: (adminId: string, body: { action: AdminMgmtAction; new_role?: string; reason?: string }) =>
    api.post<AdminListItem>(`/admin/administrators/${adminId}/actions`, body).then((r) => r.data),

  // PRD §29 global search
  search: (q: string) =>
    api.get<GlobalSearch>("/admin/search", { params: { q } }).then((r) => r.data),

  // PRD §26.7 secret descriptors
  secrets: () =>
    api.get<{ secrets: SecretDescriptor[] }>("/admin/secrets").then((r) => r.data.secrets),
};
