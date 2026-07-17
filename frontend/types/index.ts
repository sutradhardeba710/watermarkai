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
}

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  account_status: string;
  email_verified: boolean;
  created_at: string;
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
