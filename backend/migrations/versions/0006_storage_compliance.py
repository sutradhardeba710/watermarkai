"""Storage & compliance admin panel (PRD Phase 5 — §18, §21).

- video_projects: legal_hold, legal_hold_reason, processing_restricted,
  downloads_disabled (§18.5 delete-safety + §21.5 compliance actions)
- abuse_reports: severity, assigned_reviewer, resolution_note, updated_at;
  default status widened to the §21.3 vocabulary ("new")
- output_files: cleanup_failed, retention_extended (§18.3 retention dashboard)

Every added column is nullable or server-defaulted so existing rows stay valid.

Revision ID: 0006_storage_compliance
Revises: 0005_billing_admin
Create Date: 2026-07-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_storage_compliance"
down_revision: Union[str, None] = "0005_billing_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. video_projects — compliance controls (PRD §18.5, §21.5)
    # -----------------------------------------------------------------
    op.add_column("video_projects", sa.Column("legal_hold", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("video_projects", sa.Column("legal_hold_reason", sa.Text, nullable=True))
    op.add_column("video_projects", sa.Column("processing_restricted", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("video_projects", sa.Column("downloads_disabled", sa.Boolean, nullable=False, server_default=sa.text("false")))

    # -----------------------------------------------------------------
    # 2. abuse_reports — compliance triage (PRD §21.2 / §21.3)
    # -----------------------------------------------------------------
    op.add_column("abuse_reports", sa.Column("severity", sa.String(16), nullable=False, server_default="medium"))
    op.add_column("abuse_reports", sa.Column("assigned_reviewer", sa.String(36), nullable=True))
    op.add_column("abuse_reports", sa.Column("resolution_note", sa.Text, nullable=True))
    op.add_column("abuse_reports", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True))
    op.create_index(op.f("ix_abuse_reports_status"), "abuse_reports", ["status"])

    # -----------------------------------------------------------------
    # 3. output_files — retention dashboard (PRD §18.3)
    # -----------------------------------------------------------------
    op.add_column("output_files", sa.Column("cleanup_failed", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("output_files", sa.Column("retention_extended", sa.Boolean, nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("output_files", "retention_extended")
    op.drop_column("output_files", "cleanup_failed")

    op.drop_index(op.f("ix_abuse_reports_status"), table_name="abuse_reports")
    op.drop_column("abuse_reports", "updated_at")
    op.drop_column("abuse_reports", "resolution_note")
    op.drop_column("abuse_reports", "assigned_reviewer")
    op.drop_column("abuse_reports", "severity")

    op.drop_column("video_projects", "downloads_disabled")
    op.drop_column("video_projects", "processing_restricted")
    op.drop_column("video_projects", "legal_hold_reason")
    op.drop_column("video_projects", "legal_hold")
