"""Admin panel foundation (PRD Phases 1+2).

- users.admin_role (String(32), backfilled 'super_admin' for role='admin')
- video_projects.locked / moderation_note
- audit_logs: previous_data, new_data, reason, ip_hash, user_agent,
  request_id, result (+ indexes on action / created_at)
- new tables: credit_transactions, payments, support_notes

Revision ID: 0004_admin_panel
Revises: 0003
Create Date: 2026-07-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_admin_panel"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. users.admin_role + backfill legacy admins as super_admin
    # -----------------------------------------------------------------
    op.add_column("users", sa.Column("admin_role", sa.String(32), nullable=True))
    op.create_index(op.f("ix_users_admin_role"), "users", ["admin_role"])
    op.execute("UPDATE users SET admin_role = 'super_admin' WHERE role = 'admin'")

    # -----------------------------------------------------------------
    # 2. video_projects moderation columns
    # -----------------------------------------------------------------
    op.add_column(
        "video_projects",
        sa.Column("locked", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
    op.add_column("video_projects", sa.Column("moderation_note", sa.Text, nullable=True))

    # -----------------------------------------------------------------
    # 3. audit_logs traceability columns (PRD §27.2)
    # -----------------------------------------------------------------
    op.add_column("audit_logs", sa.Column("previous_data", sa.JSON, nullable=True))
    op.add_column("audit_logs", sa.Column("new_data", sa.JSON, nullable=True))
    op.add_column("audit_logs", sa.Column("reason", sa.Text, nullable=True))
    op.add_column("audit_logs", sa.Column("ip_hash", sa.String(128), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.Text, nullable=True))
    op.add_column("audit_logs", sa.Column("request_id", sa.String(64), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column("result", sa.String(16), nullable=False, server_default="success"),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"])
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"])

    # -----------------------------------------------------------------
    # 4. credit_transactions — immutable ledger (PRD §17.2)
    # -----------------------------------------------------------------
    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("balance_before", sa.Integer, nullable=False),
        sa.Column("balance_after", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("job_id", sa.String(36), nullable=True),
        sa.Column("admin_id", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_credit_transactions_user_id"), "credit_transactions", ["user_id"])
    op.create_index(op.f("ix_credit_transactions_created_at"), "credit_transactions", ["created_at"])

    # -----------------------------------------------------------------
    # 5. payments — payment history (PRD §13)
    # -----------------------------------------------------------------
    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subscription_id", sa.String(36), nullable=True),
        sa.Column("plan_id", sa.String(32), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(128), nullable=True),
        sa.Column("amount_inr", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("method", sa.String(32), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_payments_user_id"), "payments", ["user_id"])
    op.create_index(op.f("ix_payments_created_at"), "payments", ["created_at"])
    op.create_index(
        op.f("ix_payments_razorpay_payment_id"),
        "payments",
        ["razorpay_payment_id"],
        unique=True,
    )

    # -----------------------------------------------------------------
    # 6. support_notes (PRD §22)
    # -----------------------------------------------------------------
    op.create_table(
        "support_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("pinned", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(op.f("ix_support_notes_user_id"), "support_notes", ["user_id"])
    op.create_index(op.f("ix_support_notes_project_id"), "support_notes", ["project_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_support_notes_project_id"), table_name="support_notes")
    op.drop_index(op.f("ix_support_notes_user_id"), table_name="support_notes")
    op.drop_table("support_notes")

    op.drop_index(op.f("ix_payments_razorpay_payment_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_created_at"), table_name="payments")
    op.drop_index(op.f("ix_payments_user_id"), table_name="payments")
    op.drop_table("payments")

    op.drop_index(op.f("ix_credit_transactions_created_at"), table_name="credit_transactions")
    op.drop_index(op.f("ix_credit_transactions_user_id"), table_name="credit_transactions")
    op.drop_table("credit_transactions")

    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_column("audit_logs", "result")
    op.drop_column("audit_logs", "request_id")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "ip_hash")
    op.drop_column("audit_logs", "reason")
    op.drop_column("audit_logs", "new_data")
    op.drop_column("audit_logs", "previous_data")

    op.drop_column("video_projects", "moderation_note")
    op.drop_column("video_projects", "locked")

    op.drop_index(op.f("ix_users_admin_role"), table_name="users")
    op.drop_column("users", "admin_role")
