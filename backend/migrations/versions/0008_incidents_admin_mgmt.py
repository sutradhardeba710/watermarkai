"""Incidents + administrator-management fields (PRD Phase 7 — §25.3, §28.1).

Adds:
- incidents             — system-health incident timeline (§25.3)
- users.mfa_enabled / mfa_required / last_login_at / admin_created_by /
  admin_invited_at — administrator-management tracking (§28.1)

Analytics (§24), exports (§24.5), system health (§25.1/§25.2), global search
(§29) and secret handling (§26.7) are all read-only over existing tables /
config, so they need no schema changes.

Revision ID: 0008_incidents_admin_mgmt
Revises: 0007_models_presets
Create Date: 2026-07-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_incidents_admin_mgmt"
down_revision: Union[str, None] = "0007_models_presets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. incidents (PRD §25.3)
    # -----------------------------------------------------------------
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("service", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="minor"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("notes", sa.JSON, nullable=True),
        sa.Column("silenced_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(36), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(op.f("ix_incidents_status"), "incidents", ["status"])
    op.create_index(op.f("ix_incidents_started_at"), "incidents", ["started_at"])

    # -----------------------------------------------------------------
    # 2. users — administrator-management tracking (PRD §28.1)
    # -----------------------------------------------------------------
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("mfa_required", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("admin_created_by", sa.String(36), nullable=True))
    op.add_column("users", sa.Column("admin_invited_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "admin_invited_at")
    op.drop_column("users", "admin_created_by")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "mfa_required")
    op.drop_column("users", "mfa_enabled")

    op.drop_index(op.f("ix_incidents_started_at"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_status"), table_name="incidents")
    op.drop_table("incidents")
