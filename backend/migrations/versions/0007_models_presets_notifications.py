"""Models, presets, feature flags & notifications (PRD Phase 6 — §19, §20, §23, §26.5).

Creates five new tables:
- ai_models              — registered AI model versions (§19)
- processing_presets     — named processing profiles (§20)
- feature_flags          — toggleable platform capabilities (§26.5)
- notification_templates — editable email/in-app templates (§23.1/§23.2)
- broadcasts             — one-off segment announcements (§23.3)

Maintenance mode (§26.6) is stored as a JSON blob in the existing
system_settings table under key ``maintenance`` — no new table needed.

Revision ID: 0007_models_presets
Revises: 0006_storage_compliance
Create Date: 2026-07-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_models_presets"
down_revision: Union[str, None] = "0006_storage_compliance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. ai_models (PRD §19)
    # -----------------------------------------------------------------
    op.create_table(
        "ai_models",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("model_type", sa.String(64), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="testing"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_fallback", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("deployment_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supported_job_types", sa.JSON, nullable=True),
        sa.Column("supported_resolutions", sa.JSON, nullable=True),
        sa.Column("min_gpu_memory_mb", sa.Integer, nullable=True),
        sa.Column("avg_speed_fps", sa.Float, nullable=True),
        sa.Column("failure_rate", sa.Float, nullable=True),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("rollout_strategy", sa.String(32), nullable=False, server_default="internal"),
        sa.Column("rollout_percentage", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rollout_plans", sa.JSON, nullable=True),
        sa.Column("compatible_workers", sa.JSON, nullable=True),
        sa.Column("previous_version", sa.String(64), nullable=True),
        sa.Column("release_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("name", "version", name="uq_ai_models_name_version"),
    )
    op.create_index(op.f("ix_ai_models_name"), "ai_models", ["name"])
    op.create_index(op.f("ix_ai_models_status"), "ai_models", ["status"])

    # -----------------------------------------------------------------
    # 2. processing_presets (PRD §20)
    # -----------------------------------------------------------------
    op.create_table(
        "processing_presets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("required_plan", sa.String(64), nullable=True),
        sa.Column("detection_model", sa.String(128), nullable=True),
        sa.Column("tracking_model", sa.String(128), nullable=True),
        sa.Column("inpainting_model", sa.String(128), nullable=True),
        sa.Column("output_resolution", sa.String(32), nullable=True),
        sa.Column("frame_sampling_rate", sa.Integer, nullable=True),
        sa.Column("temporal_window", sa.Integer, nullable=True),
        sa.Column("mask_expansion", sa.Integer, nullable=False, server_default="0"),
        sa.Column("feathering", sa.Integer, nullable=False, server_default="4"),
        sa.Column("temporal_smoothing", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("encoding_codec", sa.String(32), nullable=False, server_default="libx264"),
        sa.Column("encoding_quality", sa.Integer, nullable=True),
        sa.Column("expected_credit_cost", sa.Integer, nullable=True),
        sa.Column("max_duration_seconds", sa.Integer, nullable=True),
        sa.Column("worker_requirements", sa.JSON, nullable=True),
        sa.Column("estimated_relative_speed", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # -----------------------------------------------------------------
    # 3. feature_flags (PRD §26.5)
    # -----------------------------------------------------------------
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_feature_flags_key"), "feature_flags", ["key"], unique=True)

    # -----------------------------------------------------------------
    # 4. notification_templates (PRD §23.1/§23.2)
    # -----------------------------------------------------------------
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("html_content", sa.Text, nullable=False, server_default=""),
        sa.Column("text_content", sa.Text, nullable=False, server_default=""),
        sa.Column("variables", sa.JSON, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_notification_templates_key"), "notification_templates", ["key"], unique=True)

    # -----------------------------------------------------------------
    # 5. broadcasts (PRD §23.3)
    # -----------------------------------------------------------------
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("target", sa.String(32), nullable=False, server_default="all"),
        sa.Column("target_plan", sa.String(64), nullable=True),
        sa.Column("recipient_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_broadcasts_created_at"), "broadcasts", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_broadcasts_created_at"), table_name="broadcasts")
    op.drop_table("broadcasts")

    op.drop_index(op.f("ix_notification_templates_key"), table_name="notification_templates")
    op.drop_table("notification_templates")

    op.drop_index(op.f("ix_feature_flags_key"), table_name="feature_flags")
    op.drop_table("feature_flags")

    op.drop_table("processing_presets")

    op.drop_index(op.f("ix_ai_models_status"), table_name="ai_models")
    op.drop_index(op.f("ix_ai_models_name"), table_name="ai_models")
    op.drop_table("ai_models")
