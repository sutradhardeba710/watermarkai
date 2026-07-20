"""Add payment tables: plans, subscriptions, credit_ledger.
Also adds plan_id and credits_remaining columns to the users table.

Revision ID: 0002_payment_tables
Revises: 0001_initial
Create Date: 2026-07-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_payment_tables"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Use the PostgreSQL ENUM variant with create_type=False so table DDL never
# auto-emits CREATE TYPE. The generic sa.Enum(create_type=...) kwarg is not
# reliably carried onto the PG variant, which caused a double CREATE TYPE
# (explicit .create() below + create_table) → DuplicateObject in one txn.
SUBSCRIPTION_STATUS = postgresql.ENUM(
    "active", "past_due", "cancelled", "trialing",
    name="subscriptionstatus",
    create_type=False,
)


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. plans table (must exist before FK in users / subscriptions)
    # -----------------------------------------------------------------
    op.create_table(
        "plans",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("price_inr", sa.Integer, nullable=False),
        sa.Column("credits_per_day", sa.Integer, nullable=False),
        sa.Column("razorpay_plan_id", sa.String(128), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Seed the three plans immediately so existing users aren't broken.
    op.bulk_insert(
        sa.table(
            "plans",
            sa.column("id", sa.String),
            sa.column("name", sa.String),
            sa.column("price_inr", sa.Integer),
            sa.column("credits_per_day", sa.Integer),
            sa.column("is_active", sa.Boolean),
        ),
        [
            {"id": "free",    "name": "Free",    "price_inr": 0,       "credits_per_day": 500,  "is_active": True},
            {"id": "starter", "name": "Starter", "price_inr": 409900,  "credits_per_day": 1000, "is_active": True},
            {"id": "pro",     "name": "Pro",     "price_inr": 1679900, "credits_per_day": 2000, "is_active": True},
        ],
    )

    # -----------------------------------------------------------------
    # 2. Add plan_id + credits_remaining to users
    # -----------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "plan_id",
            sa.String(32),
            sa.ForeignKey("plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column("credits_remaining", sa.Integer, server_default="500", nullable=False),
    )
    op.create_index("ix_users_plan_id", "users", ["plan_id"])

    # -----------------------------------------------------------------
    # 3. subscriptions table
    # -----------------------------------------------------------------
    SUBSCRIPTION_STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            index=True,
            nullable=False,
        ),
        sa.Column("plan_id", sa.String(32), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("razorpay_subscription_id", sa.String(128), unique=True, nullable=False),
        sa.Column("razorpay_payment_id", sa.String(128), nullable=True),
        sa.Column(
            "status",
            SUBSCRIPTION_STATUS,
            server_default="active",
            nullable=False,
        ),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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

    # -----------------------------------------------------------------
    # 4. credit_ledger table
    # -----------------------------------------------------------------
    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True,
            index=True,
            nullable=False,
        ),
        sa.Column("credits_used_today", sa.Integer, server_default="0", nullable=False),
        sa.Column("credits_limit", sa.Integer, server_default="500", nullable=False),
        sa.Column(
            "last_reset_at",
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


def downgrade() -> None:
    op.drop_table("credit_ledger")
    op.drop_table("subscriptions")
    SUBSCRIPTION_STATUS.drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_users_plan_id", table_name="users")
    op.drop_column("users", "credits_remaining")
    op.drop_column("users", "plan_id")
    op.drop_table("plans")
