// Type mirrors of backend schemas (SRS §15). Added incrementally per phase.

export type UserRole = "user" | "admin";
export type QualityMode = "fast" | "balanced" | "high";

export interface ProjectStatus {
  status:
    | "created"
    | "uploading"
    | "uploaded"
    | "analyzing"
    | "awaiting_review"
    | "preview_queued"
    | "preview_processing"
    | "preview_ready"
    | "processing_queued"
    | "processing"
    | "encoding"
    | "completed"
    | "failed"
    | "cancelled"
    | "expired";
}

export interface VideoProject {
  id: string;
  title: string;
  original_filename: string;
  status: ProjectStatus["status"];
  duration?: number;
  width?: number;
  height?: number;
  fps?: number;
  video_codec?: string;
  audio_codec?: string;
  has_audio?: boolean;
  file_size?: number;
  proxy_storage_key?: string | null;
  thumbnail_storage_key?: string | null;
  input_storage_key?: string | null;
  output_storage_key?: string | null;
  preview_storage_key?: string | null;
  // Short-lived signed URLs for raw <video>/<img> playback (no bearer header
  // can be attached to a media-element src). Absent until the artifact exists.
  proxy_url?: string | null;
  thumbnail_url?: string | null;
  preview_url?: string | null;
  before_preview_url?: string | null;
  created_at: string;
  completed_at?: string | null;
  expires_at?: string | null;
}

export interface UploadInitiateResponse {
  upload_id: string;
  project_id: string;
  storage_key: string;
  bucket: string;
  chunked: boolean;
  upload_url?: string | null;
}

export interface UploadCompleteResponse {
  upload_id: string;
  project_id: string;
  received_bytes: number;
  completed: boolean;
  project: VideoProject;
}

export interface ComplianceConfirmation {
  id: string;
  project_id: string;
  user_id: string;
  confirmation_version: string;
  confirmed_at: string;
}

// Phase 5 — processing
export type JobState =
  | "created"
  | "processing_queued"
  | "processing"
  | "encoding"
  | "completed"
  | "failed"
  | "cancelled"
  | "expired";

export interface JobStatus {
  id: string;
  project_id: string;
  job_type: string;
  status: JobState;
  progress: number;
  current_stage?: string | null;
  processing_mode: QualityMode;
  frames_processed: number;
  total_frames: number;
  error_code?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface ProcessResponse {
  job_id: string;
  project_id: string;
  status: JobState;
}

export interface JobEvent {
  stage: string;
  progress: number;
  frames_processed: number;
  total_frames: number;
  warnings: string[];
  message?: string | null;
  terminal: boolean;
  error_code?: string | null;
}

// Phase 6 — preview + download
export interface PreviewRequest {
  start_seconds?: number;
  duration_seconds?: 3 | 5 | 10;
}

export interface PreviewResponse {
  project_id: string;
  status: "ready" | "processing" | "queued" | "failed";
  quality_mode: QualityMode;
  start_seconds: number;
  duration_seconds: number;
  artifact_storage_key?: string | null;
  before_artifact_storage_key?: string | null;
  expires_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface DownloadUrlResponse {
  bucket: string;
  key: string;
  url: string;
  expires_seconds: number;
  expires_at: string;
}

// Phase 7 — AI detection
export interface AnalyzeResponse {
  job_id: string;
  project_id: string;
  status: string;
}

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface WatermarkCandidate {
  id: string;
  project_id: string;
  candidate_type: string;
  confidence: number;
  bounding_box: BoundingBox;
  is_static: boolean;
  start_time?: number | null;
  end_time?: number | null;
  tracking_data?: Record<string, unknown> | null;
  user_approved: boolean;
  created_at: string;
}

export interface CandidateListResponse {
  project_id: string;
  candidates: WatermarkCandidate[];
  needs_manual_selection: boolean;
  notes?: string | null;
}

export interface ApproveCandidateRequest {
  mask_expansion?: number;
  mask_feathering?: number;
  temporal_smoothing?: boolean;
}

export interface ApproveCandidateResponse {
  candidate_id: string;
  project_id: string;
  mask_id: string;
  message: string;
}

// Phase 8 — admin
export interface AdminOverview {
  total_users: number;
  active_users: number;
  suspended_users: number;
  jobs_today: number;
  queue_length: number;
  completed_jobs: number;
  failed_jobs: number;
  gpu_workers: number;
  storage_bytes: number;
  avg_processing_seconds?: number | null;
  // Admin panel Phases 1+2 (PRD §7.2)
  users_today?: number | null;
  users_this_month?: number | null;
  projects_today?: number | null;
  jobs_completed_today?: number | null;
  jobs_failed_today?: number | null;
  success_rate?: number | null;
  active_subscriptions?: number | null;
  revenue_this_month_inr?: number | null;
}

export type AdminRole =
  | "super_admin"
  | "operations"
  | "support"
  | "billing"
  | "compliance"
  | "analyst";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminMe {
  id: string;
  email: string;
  full_name: string;
  admin_role: AdminRole | "";
  permissions: string[];
}

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  admin_role?: AdminRole | null;
  account_status: string;
  email_verified: boolean;
  created_at: string;
  plan_id?: string | null;
  credits_remaining?: number | null;
  project_count: number;
  job_count: number;
}

export interface AdminJob {
  id: string;
  project_id: string;
  user_id: string;
  job_type: string;
  status: JobState;
  progress: number;
  current_stage?: string | null;
  processing_mode: QualityMode;
  worker_id?: string | null;
  attempt_count: number;
  frames_processed: number;
  total_frames: number;
  error_code?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface WorkerInfo {
  name: string;
  online: boolean;
  status?: string | null;
  gpu_name?: string | null;
  gpu_memory?: number | null;
  active_job_id?: string | null;
  last_heartbeat?: string | null;
  software_version?: string | null;
}

// Admin panel Phase 3 (PRD §10–12)
export interface JobStageStep {
  stage: string;
  state: "done" | "current" | "pending" | "skipped" | "failed" | "cancelled" | "expired";
  label: string;
}

export interface AdminJobDetail extends AdminJob {
  project_title?: string | null;
  user_email?: string | null;
  duration_seconds?: number | null;
  queued_seconds?: number | null;
  timeline: JobStageStep[];
  recent_events: AuditEntry[];
}

export interface QueueInfo {
  name: string;
  queued: number;
  active: number;
  failed_today: number;
  oldest_queued_seconds?: number | null;
}

export interface QueueMetrics {
  queued: number;
  active: number;
  completed_today: number;
  failed_today: number;
  by_state: Record<string, number>;
  queues: QueueInfo[];
}

export interface WorkerDetail extends WorkerInfo {
  active_job?: AdminJob | null;
  recent_jobs: AdminJob[];
  completed_count: number;
  failed_count: number;
}

export interface SystemConfig {
  max_file_size_mb: number;
  max_duration_seconds: number;
  max_width: number;
  max_height: number;
  max_fps: number;
  allowed_upload_extensions: string[];
  retain_original_hours: number;
  retain_preview_hours: number;
  retain_output_days: number;
  retain_failed_hours: number;
  worker_concurrency: number;
  max_retries: number;
  enabled_models: string[];
  maintenance_mode: boolean;
}

export interface SystemConfigUpdate {
  max_file_size_mb?: number;
  max_duration_seconds?: number;
  max_width?: number;
  max_height?: number;
  max_fps?: number;
  allowed_upload_extensions?: string[];
  retain_original_hours?: number;
  retain_preview_hours?: number;
  retain_output_days?: number;
  retain_failed_hours?: number;
  worker_concurrency?: number;
  max_retries?: number;
  enabled_models?: string[];
  maintenance_mode?: boolean;
}

export interface AuditEntry {
  id: string;
  actor_id?: string | null;
  action: string;
  target_type?: string | null;
  target_id?: string | null;
  details?: Record<string, unknown> | null;
  previous_data?: Record<string, unknown> | null;
  new_data?: Record<string, unknown> | null;
  reason?: string | null;
  ip_hash?: string | null;
  user_agent?: string | null;
  request_id?: string | null;
  result?: string | null;
  created_at: string;
}

export interface AbuseReportSummary {
  id: string;
  project_id?: string | null;
  reported_by?: string | null;
  reason: string;
  status: string;
  created_at: string;
}

export type UserAction = "suspend" | "reactivate";
export type JobAction = "retry" | "cancel";
export type AbuseAction = "dismiss" | "escalate" | "suspend_reporter";

export interface ActionResponse {
  id: string;
  status: string;
  account_status?: string;
}

// Admin panel Phases 1+2 (PRD §8, §9, §17, §22)

export type AdminUserAction =
  | "verify_email"
  | "resend_verification"
  | "force_password_reset"
  | "revoke_sessions"
  | "suspend"
  | "ban"
  | "restore"
  | "delete_account";

export type AdminProjectAction =
  | "extend_retention"
  | "expire_now"
  | "lock"
  | "unlock"
  | "delete_files";

export interface CreditTransaction {
  id: string;
  user_id: string;
  amount: number;
  direction: "credit" | "debit";
  balance_before: number;
  balance_after: number;
  reason?: string | null;
  source: string;
  project_id?: string | null;
  job_id?: string | null;
  admin_id?: string | null;
  created_at: string;
}

export interface Payment {
  id: string;
  user_id: string;
  subscription_id?: string | null;
  plan_id?: string | null;
  razorpay_payment_id?: string | null;
  amount_inr: number;
  currency: string;
  status: string;
  method?: string | null;
  description?: string | null;
  created_at: string;
}

export interface SupportNote {
  id: string;
  user_id: string;
  project_id?: string | null;
  author_id: string;
  body: string;
  pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminSubscription {
  id: string;
  plan_id: string;
  status: string;
  razorpay_subscription_id?: string | null;
  current_period_start?: string | null;
  current_period_end?: string | null;
  cancelled_at?: string | null;
  created_at: string;
}

export interface AdminSession {
  id: string;
  user_agent?: string | null;
  ip_hash?: string | null;
  created_at: string;
  expires_at: string;
  revoked: boolean;
}

export interface AdminUserDetail {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  admin_role?: AdminRole | null;
  account_status: string;
  email_verified: boolean;
  created_at: string;
  plan_id?: string | null;
  plan_name?: string | null;
  credits_remaining: number;
  credits_limit?: number | null;
  credits_used_today?: number | null;
  project_count: number;
  job_count: number;
  failed_job_count: number;
  storage_bytes: number;
  active_session_count: number;
  subscription?: AdminSubscription | null;
}

export interface AdminProject {
  id: string;
  user_id: string;
  user_email?: string | null;
  title: string;
  original_filename: string;
  status: ProjectStatus["status"];
  duration?: number | null;
  width?: number | null;
  height?: number | null;
  file_size?: number | null;
  locked: boolean;
  deleted: boolean;
  created_at: string;
  completed_at?: string | null;
  expires_at?: string | null;
}

export interface AdminOutputFile {
  id: string;
  storage_key: string;
  bucket: string;
  file_size?: number | null;
  quality_mode: QualityMode;
  created_at: string;
  expires_at?: string | null;
}

export interface AdminCompliance {
  id: string;
  confirmation_version: string;
  confirmed_at: string;
  ip_hash?: string | null;
}

export interface AdminProjectDetail extends AdminProject {
  fps?: number | null;
  frame_count?: number | null;
  video_codec?: string | null;
  audio_codec?: string | null;
  has_audio?: boolean | null;
  moderation_note?: string | null;
  input_storage_key?: string | null;
  output_storage_key?: string | null;
  preview_storage_key?: string | null;
  jobs: AdminJob[];
  outputs: AdminOutputFile[];
  compliance: AdminCompliance[];
  notes: SupportNote[];
}

// --- Admin Panel Phase 4: billing / payments / subscriptions / plans /
//     promos / credits (PRD §13–17). Amounts are in paise (÷100 to display). ---

export interface BillingOverview {
  revenue_today_inr: number;
  revenue_month_inr: number;
  mrr_inr: number;
  active_subscriptions: number;
  new_subscriptions: number;
  renewals: number;
  cancellations: number;
  failed_payments: number;
  refunds_inr: number;
  arpu_inr: number;
}

export interface PaymentListItem {
  id: string;
  user_id: string;
  user_email?: string | null;
  plan_id?: string | null;
  amount_inr: number;
  currency: string;
  status: string;
  method?: string | null;
  razorpay_payment_id?: string | null;
  promo_code?: string | null;
  refund_status?: string | null;
  refunded_inr: number;
  manual_review: boolean;
  created_at: string;
}

export interface Refund {
  id: string;
  payment_id: string;
  user_id: string;
  amount_inr: number;
  kind: string;
  reason?: string | null;
  razorpay_refund_id?: string | null;
  status: string;
  admin_id: string;
  created_at: string;
}

export interface PaymentDetail {
  id: string;
  user_id: string;
  user_email?: string | null;
  subscription_id?: string | null;
  plan_id?: string | null;
  amount_inr: number;
  currency: string;
  status: string;
  method?: string | null;
  description?: string | null;
  discount_inr: number;
  tax_inr: number;
  credits_issued: number;
  promo_code?: string | null;
  razorpay_payment_id?: string | null;
  razorpay_order_id?: string | null;
  razorpay_subscription_id?: string | null;
  captured_at?: string | null;
  failure_reason?: string | null;
  refund_status?: string | null;
  refunded_inr: number;
  refundable_inr: number;
  manual_review: boolean;
  internal_note?: string | null;
  created_at: string;
  refunds: Refund[];
}

export interface WebhookEvent {
  id: string;
  event_type: string;
  razorpay_event_id?: string | null;
  payment_id?: string | null;
  subscription_ref?: string | null;
  signature_valid: boolean;
  status: string;
  result?: string | null;
  created_at: string;
  payload?: Record<string, unknown> | null;
}

export interface AdminSubscriptionListItem {
  id: string;
  user_id: string;
  user_email?: string | null;
  plan_id: string;
  status: string;
  display_status: string;
  cancel_at_period_end: boolean;
  payment_failures: number;
  current_period_start?: string | null;
  current_period_end?: string | null;
  grace_until?: string | null;
  cancelled_at?: string | null;
  created_at: string;
}

export type SubscriptionAction =
  | "cancel"
  | "cancel_at_period_end"
  | "resume"
  | "reactivate"
  | "change_plan";

export interface AdminPlan {
  id: string;
  name: string;
  description?: string | null;
  price_inr: number;
  annual_price_inr?: number | null;
  currency: string;
  billing_interval: string;
  credits_per_day: number;
  monthly_credits?: number | null;
  razorpay_plan_id?: string | null;
  is_active: boolean;
  archived: boolean;
  is_recommended: boolean;
  display_order: number;
  max_upload_mb?: number | null;
  max_duration_seconds?: number | null;
  max_resolution?: string | null;
  concurrent_jobs?: number | null;
  storage_allowance_mb?: number | null;
  retention_days?: number | null;
  priority_level: number;
  api_access: boolean;
  support_level?: string | null;
  subscriber_count: number;
  created_at?: string | null;
}

export interface AdminPromo {
  id: string;
  code: string;
  description?: string | null;
  discount_type: string;
  discount_value?: number | null;
  discount_percent: number;
  max_discount_inr?: number | null;
  applicable_plans?: string[] | null;
  is_active: boolean;
  sandbox_only: boolean;
  new_users_only: boolean;
  min_purchase_inr?: number | null;
  starts_at?: string | null;
  ends_at?: string | null;
  max_total_uses?: number | null;
  max_uses_per_user?: number | null;
  times_redeemed: number;
  remaining_uses?: number | null;
  razorpay_offer_id?: string | null;
  created_at?: string | null;
}

export interface CreditDashboard {
  credits_issued_today: number;
  credits_consumed_today: number;
  credits_refunded_today: number;
  bonus_credits_today: number;
  low_balance_users: AdminUser[];
}

// --- Admin Panel Phase 5: storage & compliance (PRD §18, §21) ---

export interface StorageOverview {
  total_bytes: number;
  buckets: Record<string, number>;
  estimated_cost_inr: number; // paise
  key_counts: Record<string, number>;
}

export interface RetentionItem {
  output_id: string;
  project_id: string;
  project_title?: string | null;
  bucket: string;
  storage_key: string;
  file_size?: number | null;
  expires_at?: string | null;
  legal_hold: boolean;
  retention_extended: boolean;
  cleanup_failed: boolean;
  retention_state: string;
}

export type StorageAction =
  | "extend_retention"
  | "expire_now"
  | "trigger_cleanup"
  | "retry_cleanup"
  | "lock_compliance"
  | "verify_existence";

export interface StorageActionResponse {
  id: string;
  action: string;
  expires_at?: string | null;
  locked: boolean;
  result: Record<string, unknown>;
}

export interface ComplianceOverview {
  ownership_confirmations: number;
  projects_reported: number;
  open_reviews: number;
  suspended_accounts: number;
  repeat_offenders: number;
  high_risk_uploads: number;
  missing_confirmations: number;
  projects_on_legal_hold: number;
}

export interface AbuseReportDetail {
  id: string;
  project_id?: string | null;
  project_title?: string | null;
  project_owner_email?: string | null;
  reported_by?: string | null;
  reporter_email?: string | null;
  reason: string;
  status: string;
  severity: string;
  assigned_reviewer?: string | null;
  resolution_note?: string | null;
  legal_hold: boolean;
  legal_hold_reason?: string | null;
  processing_restricted: boolean;
  downloads_disabled: boolean;
  previous_reports: number;
  created_at: string;
  updated_at?: string | null;
}

export type ComplianceAction =
  | "mark_safe"
  | "request_information"
  | "restrict_processing"
  | "disable_downloads"
  | "suspend_account"
  | "ban_account"
  | "place_legal_hold"
  | "remove_legal_hold"
  | "escalate"
  | "add_note"
  | "close";

export type AbuseSeverity = "low" | "medium" | "high" | "critical";

// --- Admin Panel Phase 6: models, presets, feature flags, notifications,
//     maintenance (PRD §19, §20, §23, §26.5, §26.6) ---

export type ModelType =
  | "watermark_detection"
  | "ocr_detection"
  | "segmentation"
  | "static_tracking"
  | "moving_tracking"
  | "image_inpainting"
  | "temporal_video_inpainting"
  | "artifact_detection"
  | "quality_validation";

export type ModelStatus =
  | "active"
  | "testing"
  | "disabled"
  | "deprecated"
  | "maintenance"
  | "rollback_candidate";

export type ModelAction =
  | "enable_testing"
  | "enable_production"
  | "disable"
  | "set_default"
  | "set_fallback"
  | "rollback"
  | "deprecate";

export type RolloutStrategy = "internal" | "selected_users" | "percentage" | "plans" | "full";

export interface AIModel {
  id: string;
  name: string;
  model_type: ModelType;
  version: string;
  status: ModelStatus;
  is_default: boolean;
  is_fallback: boolean;
  deployment_date?: string | null;
  supported_job_types?: string[] | null;
  supported_resolutions?: string[] | null;
  min_gpu_memory_mb?: number | null;
  avg_speed_fps?: number | null;
  failure_rate?: number | null;
  quality_score?: number | null;
  rollout_strategy: RolloutStrategy;
  rollout_percentage: number;
  rollout_plans?: string[] | null;
  compatible_workers?: string[] | null;
  previous_version?: string | null;
  release_notes?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface Preset {
  id: string;
  name: string;
  description?: string | null;
  enabled: boolean;
  is_default: boolean;
  required_plan?: string | null;
  detection_model?: string | null;
  tracking_model?: string | null;
  inpainting_model?: string | null;
  output_resolution?: string | null;
  frame_sampling_rate?: number | null;
  temporal_window?: number | null;
  mask_expansion: number;
  feathering: number;
  temporal_smoothing: boolean;
  encoding_codec: string;
  encoding_quality?: number | null;
  expected_credit_cost?: number | null;
  max_duration_seconds?: number | null;
  worker_requirements?: Record<string, unknown> | null;
  estimated_relative_speed?: number | null;
  created_at: string;
  updated_at?: string | null;
}

export interface FeatureFlag {
  key: string;
  label: string;
  enabled: boolean;
  description?: string | null;
}

export interface NotificationTemplate {
  id: string;
  key: string;
  name: string;
  subject: string;
  html_content: string;
  text_content: string;
  variables?: string[] | null;
  enabled: boolean;
  version: number;
  updated_at?: string | null;
}

export interface TemplatePreview {
  subject: string;
  html_content: string;
  text_content: string;
}

export type BroadcastKind = "in_app" | "maintenance" | "feature" | "billing" | "policy";

export type BroadcastTarget =
  | "all"
  | "specific_plan"
  | "active_subscribers"
  | "free_users"
  | "selected_users"
  | "users_with_active_jobs";

export interface BroadcastResponse {
  id: string;
  kind: string;
  target: string;
  recipient_count: number;
}

export interface MaintenanceState {
  maintenance_enabled: boolean;
  start_time?: string | null;
  end_time?: string | null;
  public_message: string;
  allow_administrators: boolean;
  allow_existing_jobs_to_finish: boolean;
  pause_new_uploads: boolean;
  pause_new_processing_jobs: boolean;
  disable_checkout: boolean;
  status_page_link?: string | null;
}

// --- Admin Panel Phase 7 (PRD §24, §25, §28, §29, §26.7) ---

export interface Analytics {
  product: Record<string, number>;
  processing: Record<string, unknown>;
  business: Record<string, unknown>;
  cost: Record<string, number>;
  window_days?: number | null;
}

export type ExportDataset = "users" | "payments" | "jobs" | "audit";
export type ExportFormat = "csv" | "json";

export interface ServiceStatus {
  name: string;
  status: "operational" | "down" | "unknown";
  detail?: string | null;
  latency_ms?: number | null;
}

export interface HealthMetric {
  metric: string;
  value?: number | null;
  status: "ok" | "warn" | "critical" | "unknown";
  unit?: string | null;
}

export interface SystemHealth {
  overall: string;
  services: ServiceStatus[];
  metrics: HealthMetric[];
  checked_at: string;
}

export type IncidentSeverity = "info" | "minor" | "major" | "critical";
export type IncidentStatus = "open" | "monitoring" | "resolved";
export type IncidentAction =
  | "acknowledge"
  | "silence"
  | "add_note"
  | "resolve"
  | "reopen";

export interface Incident {
  id: string;
  service: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  title: string;
  detail?: string | null;
  notes?: Array<{ by: string; note: string }> | null;
  silenced_until?: string | null;
  started_at?: string | null;
  resolved_at?: string | null;
}

export type AdminMgmtAction =
  | "assign_role"
  | "change_role"
  | "suspend"
  | "reactivate"
  | "revoke_sessions"
  | "require_password_reset"
  | "require_mfa"
  | "remove";

export interface AdminListItem {
  id: string;
  email: string;
  full_name: string;
  admin_role?: string | null;
  account_status: string;
  mfa_enabled: boolean;
  last_login_at?: string | null;
  created_at?: string | null;
  admin_created_by?: string | null;
}

export interface SearchResultItem {
  id: string;
  label: string;
  sublabel?: string | null;
}

export interface SearchGroup {
  entity_type: string;
  items: SearchResultItem[];
}

export interface GlobalSearch {
  query: string;
  groups: SearchGroup[];
}

export interface SecretDescriptor {
  name: string;
  configured: boolean;
  public: boolean;
  value?: string | null;
  last_four: string;
  updated_at?: string | null;
}
