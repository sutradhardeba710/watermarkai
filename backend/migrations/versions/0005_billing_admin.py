"""Billing admin panel (PRD Phases 4 — §13–17).

- plans: annual_price_inr, currency, billing_interval, display_order,
  is_recommended, archived, monthly_credits, max_upload_mb,
  max_duration_seconds, max_resolution, concurrent_jobs,
  storage_allowance_mb, retention_days, priority_level, api_access,
  support_level
- subscriptions: cancel_at_period_end, payment_failures, grace_until,
  credits_allocated
- promo_codes: description, discount_type, discount_value, max_discount_inr,
  applicable_plans, starts_at, ends_at, max_total_uses, max_uses_per_user,
  min_purchase_inr, new_users_only, sandbox_only, times_redeemed
- payments: discount_inr, tax_inr, razorpay_order_id,
  razorpay_subscription_id, promo_code, credits_issued, captured_at,
  failure_reason, refund_status, refunded_inr, manual_review, internal_note
- new tables: refunds, webhook_events

Every added column is nullable or server-defaulted so existing rows stay valid.

Revision ID: 0005_billing_admin
Revises: 0004_admin_panel
Create Date: 2026-07-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_billing_admin"
down_revision: Union[str, None] = "0004_admin_panel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. plans — admin plan management (PRD §15.2)
    # -----------------------------------------------------------------
    op.add_column("plans", sa.Column("annual_price_inr", sa.Integer, nullable=True))
    op.add_column("plans", sa.Column("currency", sa.String(8), nullable=False, server_default="INR"))
    op.add_column("plans", sa.Column("billing_interval", sa.String(16), nullable=False, server_default="monthly"))
    op.add_column("plans", sa.Column("display_order", sa.Integer, nullable=False, server_default="0"))
    op.add_column("plans", sa.Column("is_recommended", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("plans", sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("plans", sa.Column("monthly_credits", sa.Integer, nullable=True))
    op.add_column("plans", sa.Column("max_upload_mb", sa.Integer, nullable=True))
    op.add_column("plans", sa.Column("max_duration_seconds", sa.Integer, nullable=True))
    op.add_column("plans", sa.Column("max_resolution", sa.String(16), nullable=True))
    op.add_column("plans", sa.Column("concurrent_jobs", sa.Integer, nullable=True))
    op.add_column("plans", sa.Column("storage_allowance_mb", sa.Integer, nullable=True))
    op.add_column("plans", sa.Column("retention_days", sa.Integer, nullable=True))
    op.add_column("plans", sa.Column("priority_level", sa.Integer, nullable=False, server_default="0"))
    op.add_column("plans", sa.Column("api_access", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("plans", sa.Column("support_level", sa.String(32), nullable=True))

    # -----------------------------------------------------------------
    # 2. subscriptions — admin subscription management (PRD §14)
    # -----------------------------------------------------------------
    op.add_column("subscriptions", sa.Column("cancel_at_period_end", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("subscriptions", sa.Column("payment_failures", sa.Integer, nullable=False, server_default="0"))
    op.add_column("subscriptions", sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("credits_allocated", sa.Integer, nullable=True))

    # -----------------------------------------------------------------
    # 3. promo_codes — admin promo management (PRD §16.1)
    # -----------------------------------------------------------------
    op.add_column("promo_codes", sa.Column("description", sa.Text, nullable=True))
    op.add_column("promo_codes", sa.Column("discount_type", sa.String(24), nullable=False, server_default="percentage"))
    op.add_column("promo_codes", sa.Column("discount_value", sa.Integer, nullable=True))
    op.add_column("promo_codes", sa.Column("max_discount_inr", sa.Integer, nullable=True))
    op.add_column("promo_codes", sa.Column("applicable_plans", sa.JSON, nullable=True))
    op.add_column("promo_codes", sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("promo_codes", sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("promo_codes", sa.Column("max_total_uses", sa.Integer, nullable=True))
    op.add_column("promo_codes", sa.Column("max_uses_per_user", sa.Integer, nullable=True))
    op.add_column("promo_codes", sa.Column("min_purchase_inr", sa.Integer, nullable=True))
    op.add_column("promo_codes", sa.Column("new_users_only", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("promo_codes", sa.Column("sandbox_only", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("promo_codes", sa.Column("times_redeemed", sa.Integer, nullable=False, server_default="0"))
    # Mark the seeded sandbox promo as sandbox-only (PRD §16.4).
    op.execute("UPDATE promo_codes SET sandbox_only = true WHERE code = 'SANDBOX50'")

    # -----------------------------------------------------------------
    # 4. payments — admin payment detail (PRD §13.2)
    # -----------------------------------------------------------------
    op.add_column("payments", sa.Column("discount_inr", sa.Integer, nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("tax_inr", sa.Integer, nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("razorpay_order_id", sa.String(128), nullable=True))
    op.add_column("payments", sa.Column("razorpay_subscription_id", sa.String(128), nullable=True))
    op.add_column("payments", sa.Column("promo_code", sa.String(32), nullable=True))
    op.add_column("payments", sa.Column("credits_issued", sa.Integer, nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("failure_reason", sa.Text, nullable=True))
    op.add_column("payments", sa.Column("refund_status", sa.String(24), nullable=True))
    op.add_column("payments", sa.Column("refunded_inr", sa.Integer, nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("manual_review", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("payments", sa.Column("internal_note", sa.Text, nullable=True))

    # -----------------------------------------------------------------
    # 5. refunds (PRD §13.5)
    # -----------------------------------------------------------------
    op.create_table(
        "refunds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("amount_inr", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("razorpay_refund_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="processed"),
        sa.Column("admin_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(op.f("ix_refunds_payment_id"), "refunds", ["payment_id"])
    op.create_index(op.f("ix_refunds_user_id"), "refunds", ["user_id"])
    op.create_index(op.f("ix_refunds_created_at"), "refunds", ["created_at"])

    # -----------------------------------------------------------------
    # 6. webhook_events (PRD §13.4 / §26)
    # -----------------------------------------------------------------
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("razorpay_event_id", sa.String(128), nullable=True),
        sa.Column("payment_id", sa.String(36), nullable=True),
        sa.Column("subscription_ref", sa.String(128), nullable=True),
        sa.Column("signature_valid", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(24), nullable=False, server_default="processed"),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(op.f("ix_webhook_events_event_type"), "webhook_events", ["event_type"])
    op.create_index(op.f("ix_webhook_events_payment_id"), "webhook_events", ["payment_id"])
    op.create_index(op.f("ix_webhook_events_created_at"), "webhook_events", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_webhook_events_created_at"), table_name="webhook_events")
    op.drop_index(op.f("ix_webhook_events_payment_id"), table_name="webhook_events")
    op.drop_index(op.f("ix_webhook_events_event_type"), table_name="webhook_events")
    op.drop_table("webhook_events")

    op.drop_index(op.f("ix_refunds_created_at"), table_name="refunds")
    op.drop_index(op.f("ix_refunds_user_id"), table_name="refunds")
    op.drop_index(op.f("ix_refunds_payment_id"), table_name="refunds")
    op.drop_table("refunds")

    for col in (
        "internal_note", "manual_review", "refunded_inr", "refund_status",
        "failure_reason", "captured_at", "credits_issued", "promo_code",
        "razorpay_subscription_id", "razorpay_order_id", "tax_inr", "discount_inr",
    ):
        op.drop_column("payments", col)

    for col in (
        "times_redeemed", "sandbox_only", "new_users_only", "min_purchase_inr",
        "max_uses_per_user", "max_total_uses", "ends_at", "starts_at",
        "applicable_plans", "max_discount_inr", "discount_value", "discount_type",
        "description",
    ):
        op.drop_column("promo_codes", col)

    for col in ("credits_allocated", "grace_until", "payment_failures", "cancel_at_period_end"):
        op.drop_column("subscriptions", col)

    for col in (
        "support_level", "api_access", "priority_level", "retention_days",
        "storage_allowance_mb", "concurrent_jobs", "max_resolution",
        "max_duration_seconds", "max_upload_mb", "monthly_credits", "archived",
        "is_recommended", "display_order", "billing_interval", "currency",
        "annual_price_inr",
    ):
        op.drop_column("plans", col)
