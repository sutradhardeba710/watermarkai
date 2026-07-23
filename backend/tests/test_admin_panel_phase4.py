"""Admin Panel Phase 4 pure-logic tests — billing / payments / subscriptions /
plans / promos / credits policy (PRD §13–17).

No DB / SQLAlchemy — runs on the 32-bit dev box.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import admin_service as svc
from app.services import payment_service


# ---------------------------------------------------------------------------
# mask_secret (PRD §13.4, §33.2)
# ---------------------------------------------------------------------------


def test_mask_secret_keeps_last_four():
    masked = svc.mask_secret("pay_ABCDEFGH1234")
    assert masked.endswith("1234")
    assert masked[:-4] == "•" * (len("pay_ABCDEFGH1234") - 4)


def test_mask_secret_short_value_fully_masked():
    assert svc.mask_secret("abcd") == "••••"
    assert svc.mask_secret("ab") == "••"


def test_mask_secret_none_passthrough():
    assert svc.mask_secret(None) is None
    assert svc.mask_secret("") == ""


# ---------------------------------------------------------------------------
# refund approval + validation (PRD §13.5)
# ---------------------------------------------------------------------------


def test_refund_requires_approval_above_threshold_for_non_super():
    assert svc.refund_requires_approval(500_000, actor_role="billing") is True
    assert svc.refund_requires_approval(600_000, actor_role="operations") is True


def test_refund_super_admin_never_needs_approval():
    assert svc.refund_requires_approval(10_000_000, actor_role="super_admin") is False


def test_refund_below_threshold_no_approval():
    assert svc.refund_requires_approval(499_999, actor_role="billing") is False


def test_validate_refund_full_vs_partial():
    assert svc.validate_refund(amount_inr=409900, payment_amount_inr=409900, already_refunded_inr=0) == "full"
    assert svc.validate_refund(amount_inr=100000, payment_amount_inr=409900, already_refunded_inr=0) == "partial"


def test_validate_refund_second_partial_completes_full():
    # 300k already refunded, refunding the remaining 109900 → full
    kind = svc.validate_refund(amount_inr=109900, payment_amount_inr=409900, already_refunded_inr=300000)
    assert kind == "full"


def test_validate_refund_rejects_overdraw_and_nonpositive():
    with pytest.raises(ValueError):
        svc.validate_refund(amount_inr=500000, payment_amount_inr=409900, already_refunded_inr=0)
    with pytest.raises(ValueError):
        svc.validate_refund(amount_inr=0, payment_amount_inr=409900, already_refunded_inr=0)
    with pytest.raises(ValueError):
        svc.validate_refund(amount_inr=1, payment_amount_inr=409900, already_refunded_inr=409900)


def test_refund_status_after():
    assert svc.refund_status_after(409900, 0) == "none"
    assert svc.refund_status_after(409900, 100000) == "partial"
    assert svc.refund_status_after(409900, 409900) == "full"
    assert svc.refund_status_after(409900, 500000) == "full"


# ---------------------------------------------------------------------------
# billing overview (PRD §13.1)
# ---------------------------------------------------------------------------


def test_billing_overview_computes_arpu():
    out = svc.billing_overview(
        {"revenue_today_inr": 50000, "revenue_this_month_inr": 4000000, "failed_payments": 3},
        active_subscriptions=10,
    )
    assert out["revenue_month_inr"] == 4000000
    assert out["mrr_inr"] == 4000000
    assert out["arpu_inr"] == 400000
    assert out["active_subscriptions"] == 10
    assert out["failed_payments"] == 3


def test_billing_overview_zero_subscriptions_arpu_zero():
    out = svc.billing_overview({"revenue_this_month_inr": 4000000}, active_subscriptions=0)
    assert out["arpu_inr"] == 0


def test_billing_overview_defaults_all_zero():
    out = svc.billing_overview({})
    assert out["revenue_today_inr"] == 0
    assert out["arpu_inr"] == 0
    assert out["refunds_inr"] == 0


# ---------------------------------------------------------------------------
# promo helpers (PRD §16)
# ---------------------------------------------------------------------------


def test_promo_remaining_uses():
    assert svc.promo_remaining_uses(100, 40) == 60
    assert svc.promo_remaining_uses(100, 120) == 0  # clamped
    assert svc.promo_remaining_uses(None, 40) is None  # unlimited


def test_validate_promo_fields_ok():
    svc.validate_promo_fields(discount_type="percentage", discount_value=50)
    svc.validate_promo_fields(discount_type="fixed", discount_value=10000, max_total_uses=100)
    svc.validate_promo_fields(discount_type="bonus_credits", discount_value=500)


def test_validate_promo_fields_rejects():
    with pytest.raises(ValueError):
        svc.validate_promo_fields(discount_type="nonsense", discount_value=10)
    with pytest.raises(ValueError):
        svc.validate_promo_fields(discount_type="percentage", discount_value=150)
    with pytest.raises(ValueError):
        svc.validate_promo_fields(discount_type="fixed", discount_value=-5)
    with pytest.raises(ValueError):
        svc.validate_promo_fields(discount_type="fixed", discount_value=10, max_uses_per_user=-1)


# ---------------------------------------------------------------------------
# plan validation (PRD §15.2)
# ---------------------------------------------------------------------------


def test_validate_plan_fields_ok():
    svc.validate_plan_fields(price_inr=409900, credits_per_day=1000, billing_interval="monthly")
    svc.validate_plan_fields(price_inr=0, credits_per_day=500)


def test_validate_plan_fields_rejects():
    with pytest.raises(ValueError):
        svc.validate_plan_fields(price_inr=-1, credits_per_day=100)
    with pytest.raises(ValueError):
        svc.validate_plan_fields(price_inr=100, credits_per_day=-1)
    with pytest.raises(ValueError):
        svc.validate_plan_fields(price_inr=100, credits_per_day=100, billing_interval="weekly")


# ---------------------------------------------------------------------------
# credit dashboard (PRD §17.1)
# ---------------------------------------------------------------------------


def test_credit_dashboard_splits_by_direction_and_source():
    rows = [
        {"direction": "credit", "amount": 1000, "source": "subscription"},
        {"direction": "credit", "amount": 200, "source": "refund"},
        {"direction": "credit", "amount": 50, "source": "admin"},
        {"direction": "debit", "amount": 300, "source": "job"},
        {"direction": "debit", "amount": 100, "source": "job"},
    ]
    out = svc.credit_dashboard(rows)
    assert out["credits_issued_today"] == 1250   # all credits
    assert out["credits_consumed_today"] == 400  # all debits
    assert out["credits_refunded_today"] == 200
    assert out["bonus_credits_today"] == 1050    # subscription + admin


def test_credit_dashboard_empty():
    out = svc.credit_dashboard([])
    assert out == {
        "credits_issued_today": 0,
        "credits_consumed_today": 0,
        "credits_refunded_today": 0,
        "bonus_credits_today": 0,
    }


# ---------------------------------------------------------------------------
# subscription display status (PRD §14.3)
# ---------------------------------------------------------------------------


def test_subscription_grace_window_shows_past_due():
    now = datetime(2026, 7, 19, tzinfo=timezone.utc)
    grace = now + timedelta(days=2)
    assert svc.subscription_display_status("active", grace_until=grace, now=now) == "past_due"


def test_subscription_expired_grace_ignored():
    now = datetime(2026, 7, 19, tzinfo=timezone.utc)
    grace = now - timedelta(days=1)
    assert svc.subscription_display_status("active", grace_until=grace, now=now) == "active"


def test_subscription_cancelled_stays_cancelled_despite_grace():
    now = datetime(2026, 7, 19, tzinfo=timezone.utc)
    grace = now + timedelta(days=2)
    assert svc.subscription_display_status("cancelled", grace_until=grace, now=now) == "cancelled"


# ---------------------------------------------------------------------------
# status vocabularies present (PRD §13.3 / §14.3 / §16.2)
# ---------------------------------------------------------------------------


def test_status_vocabularies_complete():
    assert "captured" in svc.PAYMENT_STATUSES and "sandbox" in svc.PAYMENT_STATUSES
    assert "paused" in svc.SUBSCRIPTION_STATUSES and "past_due" in svc.SUBSCRIPTION_STATUSES
    assert "percentage" in svc.DISCOUNT_TYPES and "bonus_credits" in svc.DISCOUNT_TYPES


# ---------------------------------------------------------------------------
# webhook payload masking (PRD §13.4)
# ---------------------------------------------------------------------------


def test_mask_webhook_payload_masks_sensitive_keys_recursively():
    payload = {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_ABCDEFGH1234",
                    "email": "person@example.com",
                    "card": "4111111111111234",
                    "amount": 409900,
                }
            }
        },
    }
    out = svc.mask_webhook_payload(payload)
    entity = out["payload"]["payment"]["entity"]
    # Non-sensitive scalars pass through untouched.
    assert out["event"] == "payment.captured"
    assert entity["id"] == "pay_ABCDEFGH1234"
    assert entity["amount"] == 409900
    # Sensitive keys are masked but keep their last 4.
    assert entity["email"] != "person@example.com"  # masked, not raw
    assert entity["email"].endswith(".com")
    assert "•" in entity["email"]
    assert entity["card"].endswith("1234")
    assert "•" in entity["card"]


def test_mask_webhook_payload_handles_lists_and_scalars():
    assert svc.mask_webhook_payload(None) is None
    assert svc.mask_webhook_payload("plain") == "plain"
    out = svc.mask_webhook_payload([{"token": "tok_ABCD1234"}, {"amount": 10}])
    assert out[0]["token"].endswith("1234") and "•" in out[0]["token"]
    assert out[1]["amount"] == 10

def test_fixed_promo_discount_uses_paise_amount():
    promo = SimpleNamespace(
        discount_type="fixed",
        discount_value=20_000,
        discount_percent=0,
        max_discount_inr=None,
    )

    assert payment_service.compute_promo_discount(promo, price_paise=50_000) == 20_000
