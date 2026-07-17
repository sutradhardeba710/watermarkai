"""initial schema — all tables from PRD §14 / SRS §8

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# enum name consts
USER_ROLE = sa.Enum("user", "admin", name="userrole")
ACCOUNT_STATUS = sa.Enum("active", "suspended", "deleted", name="accountstatus")
PROJECT_STATUS = sa.Enum(
    "created", "uploading", "uploaded", "analyzing", "awaiting_review",
    "preview_queued", "preview_processing", "preview_ready",
    "processing_queued", "processing", "encoding",
    "completed", "failed", "cancelled", "expired",
    name="projectstatus",
)
JOB_STATE = sa.Enum(
    "created", "uploading", "uploaded", "analyzing", "awaiting_review",
    "preview_queued", "preview_processing", "preview_ready",
    "processing_queued", "processing", "encoding",
    "completed", "failed", "cancelled", "expired",
    name="jobstate",
)
JOB_TYPE = sa.Enum("analyze", "track", "preview", "process", "encode", name="jobtype")
QUALITY_MODE = sa.Enum("fast", "balanced", "high", name="qualitymode")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("role", USER_ROLE, nullable=False, server_default=sa.text("'user'")),
        sa.Column("account_status", ACCOUNT_STATUS, nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(255), nullable=False),
        sa.Column("user_agent", sa.Text),
        sa.Column("ip_hash", sa.String(128)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "video_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("input_storage_key", sa.String(1024)),
        sa.Column("output_storage_key", sa.String(1024)),
        sa.Column("preview_storage_key", sa.String(1024)),
        sa.Column("status", PROJECT_STATUS, nullable=False, server_default=sa.text("'created'")),
        sa.Column("duration", sa.Float),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("fps", sa.Float),
        sa.Column("frame_count", sa.Integer),
        sa.Column("video_codec", sa.String(64)),
        sa.Column("audio_codec", sa.String(64)),
        sa.Column("has_audio", sa.Boolean),
        sa.Column("file_size", sa.Integer),
        sa.Column("proxy_storage_key", sa.String(1024)),
        sa.Column("thumbnail_storage_key", sa.String(1024)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("deleted", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_video_projects_user_id", "video_projects", ["user_id"])
    op.create_index("ix_video_projects_status", "video_projects", ["status"])
    op.create_index("ix_video_projects_created_at", "video_projects", ["created_at"])
    op.create_index("ix_video_projects_expires_at", "video_projects", ["expires_at"])

    op.create_table(
        "uploads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("total_bytes", sa.Integer),
        sa.Column("received_bytes", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("storage_key", sa.String(1024)),
        sa.Column("completed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_uploads_project_id", "uploads", ["project_id"])
    op.create_index("ix_uploads_user_id", "uploads", ["user_id"])

    op.create_table(
        "watermark_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_type", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("start_time", sa.Float),
        sa.Column("end_time", sa.Float),
        sa.Column("is_static", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("bounding_box", sa.JSON, nullable=False),
        sa.Column("mask_storage_key", sa.String(1024)),
        sa.Column("tracking_data", sa.JSON),
        sa.Column("user_approved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_watermark_candidates_project_id", "watermark_candidates", ["project_id"])

    op.create_table(
        "watermark_masks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool", sa.String(32), nullable=False),
        sa.Column("geometry", sa.JSON, nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("mask_expansion", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("mask_feathering", sa.Integer, nullable=False, server_default=sa.text("4")),
        sa.Column("temporal_smoothing", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("apply_to_entire", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("start_time", sa.Float),
        sa.Column("end_time", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_watermark_masks_project_id", "watermark_masks", ["project_id"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", JOB_TYPE, nullable=False),
        sa.Column("status", JOB_STATE, nullable=False, server_default=sa.text("'created'")),
        sa.Column("progress", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("current_stage", sa.String(64)),
        sa.Column("processing_mode", QUALITY_MODE, nullable=False, server_default=sa.text("'balanced'")),
        sa.Column("worker_id", sa.String(128)),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("frames_processed", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("total_frames", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.String(128)),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_processing_jobs_project_id", "processing_jobs", ["project_id"])
    op.create_index("ix_processing_jobs_user_id", "processing_jobs", ["user_id"])
    op.create_index("ix_processing_jobs_status", "processing_jobs", ["status"])
    op.create_index("ix_processing_jobs_created_at", "processing_jobs", ["created_at"])

    op.create_table(
        "processing_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quality_mode", QUALITY_MODE, nullable=False, server_default=sa.text("'balanced'")),
        sa.Column("mask_expansion", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("mask_feathering", sa.Integer, nullable=False, server_default=sa.text("4")),
        sa.Column("temporal_smoothing", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("output_resolution", sa.String(32)),
        sa.Column("output_codec", sa.String(32), nullable=False, server_default=sa.text("'libx264'")),
        sa.Column("preserve_audio", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_processing_settings_project_id", "processing_settings", ["project_id"])

    op.create_table(
        "output_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("bucket", sa.String(64), nullable=False, server_default=sa.text("'outputs'")),
        sa.Column("duration", sa.Float),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("file_size", sa.Integer),
        sa.Column("quality_mode", QUALITY_MODE, nullable=False, server_default=sa.text("'balanced'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_output_files_project_id", "output_files", ["project_id"])
    op.create_index("ix_output_files_created_at", "output_files", ["created_at"])
    op.create_index("ix_output_files_expires_at", "output_files", ["expires_at"])

    op.create_table(
        "compliance_confirmations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confirmation_version", sa.String(32), nullable=False, server_default=sa.text("'1.0'")),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ip_hash", sa.String(128)),
        sa.Column("user_agent", sa.Text),
    )
    op.create_index("ix_compliance_confirmations_user_id", "compliance_confirmations", ["user_id"])
    op.create_index("ix_compliance_confirmations_project_id", "compliance_confirmations", ["project_id"])

    op.create_table(
        "worker_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'idle'")),
        sa.Column("gpu_name", sa.String(255)),
        sa.Column("gpu_memory", sa.Integer),
        sa.Column("active_job_id", sa.String(128)),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True)),
        sa.Column("software_version", sa.String(64)),
    )
    op.create_index("ix_worker_nodes_status", "worker_nodes", ["status"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(36)),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36)),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(64)),
        sa.Column("target_id", sa.String(36)),
        sa.Column("details", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])

    op.create_table(
        "abuse_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36)),
        sa.Column("reported_by", sa.String(36)),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_abuse_reports_project_id", "abuse_reports", ["project_id"])

    op.create_table(
        "system_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"])


def downgrade() -> None:
    for t in (
        "system_settings", "abuse_reports", "audit_logs", "notifications",
        "worker_nodes", "compliance_confirmations", "output_files",
        "processing_settings", "processing_jobs", "watermark_masks",
        "watermark_candidates", "uploads", "video_projects", "sessions", "users",
    ):
        op.drop_table(t)

    for e in ("qualitymode", "jobtype", "jobstate", "projectstatus", "accountstatus", "userrole"):
        op.execute(f"DROP TYPE IF EXISTS {e}")
