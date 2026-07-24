"""Payment service — Razorpay integration + credit management.

Design decisions
----------------
* Razorpay is imported lazily so the service stays importable on
  machines where the SDK is not yet installed (graceful degradation).
* All DB mutations are kept out of the webhook handler body; the
  route layer commits after this service returns.
* Credit deduction is atomic via an UPDATE … WHERE credits_remaining >= cost
  pattern; the route layer raises 402 if the update affected 0 rows.
* A ``RAZORPAY_SANDBOX`` mode is activated automatically when
  ``razorpay_key_id`` is empty so local dev works without credentials.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from app.core.config import get_settings
from app.core.errors import AppError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as DbSession
    from app.models import CreditLedger, Plan, Subscription, User

logger = logging.getLogger(__name__)
settings = get_settings()

# Credits consumed per video processing job (mirrors frontend pricingPlans.ts)
CREDITS_PER_JOB = 100

# Plan data mirrors frontend pricingPlans.ts
_FREE_PLAN_DATA = {
    "id": "free",
    "name": "Free",
    "price_inr": 0,
    "credits_per_day": 500,
    "description": "Everything you need to try ClearFrame on authorized footage.",
}
_STARTER_PLAN_DATA = {
    "id": "starter",
    "name": "Starter",
    "price_inr": 409900,      # stored in paise (INR × 100)
    "credits_per_day": 1000,
    "description": "More daily capacity and priority processing.",
}
_PRO_PLAN_DATA = {
    "id": "pro",
    "name": "Pro",
    "price_inr": 1679900,
    "credits_per_day": 2000,
    "description": "Fastest lane for high-volume, repeatable cleanup.",
}

ALL_PLANS = [_FREE_PLAN_DATA, _STARTER_PLAN_DATA, _PRO_PLAN_DATA]


# ---------------------------------------------------------------------------
# Sandbox helper
# ---------------------------------------------------------------------------

def _is_sandbox() -> bool:
    return not bool(settings.razorpay_key_id and settings.razorpay_key_secret)


def _razorpay_client():
    """Return a live Razorpay client or raise if credentials are absent."""
    if _is_sandbox():
        raise AppError(
            "PAYMENT_NOT_CONFIGURED",
            "Razorpay credentials are not configured on this server. "
            "Set VWA_RAZORPAY_KEY_ID and VWA_RAZORPAY_KEY_SECRET in your .env.",
            503,
        )
    try:
        import razorpay  # noqa: PLC0415
    except ImportError as exc:
        raise AppError(
            "PAYMENT_SDK_MISSING",
            "The razorpay Python package is not installed. Run: pip install razorpay",
            503,
        ) from exc
    return razorpay.Client(
        auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
    )


# ---------------------------------------------------------------------------
# Plan catalog helpers
# ---------------------------------------------------------------------------

def get_plan(db: "DbSession", plan_id: str) -> "Plan":
    from app.models import Plan
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise AppError("NOT_FOUND", f"Plan '{plan_id}' not found.", 404)
    return plan


def get_user_plan_or_free(db: "DbSession", user: "User") -> "Plan":
    """Return the user's current plan row; falls back to the 'free' plan."""
    from app.models import Plan
    if user.plan_id:
        plan = db.get(Plan, user.plan_id)
        if plan:
            return plan
    free = db.get(Plan, "free")
    if free is None:
        raise AppError("INTERNAL_ERROR", "Plan catalog not seeded.", 500)
    return free


def seed_plans(db: "DbSession") -> None:
    """Idempotently insert the three plan rows. Called from app startup / seed.py."""
    from app.models import Plan
    for data in ALL_PLANS:
        existing = db.get(Plan, data["id"])
        if existing is None:
            plan = Plan(**data)
            # Attach Razorpay plan IDs if configured
            if data["id"] == "starter" and settings.razorpay_plan_id_starter:
                plan.razorpay_plan_id = settings.razorpay_plan_id_starter
            elif data["id"] == "pro" and settings.razorpay_plan_id_pro:
                plan.razorpay_plan_id = settings.razorpay_plan_id_pro
            db.add(plan)
        else:
            # Update Razorpay plan IDs if they've been configured since last seed
            if data["id"] == "starter" and settings.razorpay_plan_id_starter:
                existing.razorpay_plan_id = settings.razorpay_plan_id_starter
            elif data["id"] == "pro" and settings.razorpay_plan_id_pro:
                existing.razorpay_plan_id = settings.razorpay_plan_id_pro
    # Seed sandbox promo code
    from app.models import PromoCode
    sandbox_promo = db.query(PromoCode).filter_by(code="SANDBOX50").first()
    if not sandbox_promo:
        db.add(PromoCode(
            code="SANDBOX50",
            razorpay_offer_id=None,
            discount_percent=50,
            is_active=True
        ))
    db.flush()


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------

def _get_valid_promo(db: "DbSession", code: str, *, plan_id: str):
    """Look up an active promo and enforce its constraints. Returns the promo
    row or raises AppError so a bad code never silently charges full price."""
    from app.models import PromoCode

    promo = (
        db.query(PromoCode)
        .filter(PromoCode.code == code.strip().upper(), PromoCode.is_active == True)  # noqa: E712
        .first()
    )
    if promo is None:
        raise AppError("INVALID_PROMO", "Promo code is invalid or inactive.", 400)
    now = datetime.now(timezone.utc)
    starts = promo.starts_at
    ends = promo.ends_at
    if starts is not None and starts.tzinfo is None:
        starts = starts.replace(tzinfo=timezone.utc)
    if ends is not None and ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    if (starts and now < starts) or (ends and now > ends):
        raise AppError("INVALID_PROMO", "Promo code is not currently valid.", 400)
    if promo.max_total_uses is not None and promo.times_redeemed >= promo.max_total_uses:
        raise AppError("INVALID_PROMO", "Promo code has reached its usage limit.", 400)
    if promo.applicable_plans and plan_id not in promo.applicable_plans:
        raise AppError("INVALID_PROMO", "Promo code does not apply to this plan.", 400)
    if promo.sandbox_only and not _is_sandbox():
        raise AppError("INVALID_PROMO", "Promo code is not valid here.", 400)
    return promo


def compute_promo_discount(promo, price_paise: int) -> int:
    """Discount in paise for a promo applied to a price. Percentage promos use
    discount_percent (mirrored from discount_value); fixed promos use
    discount_value directly (paise). Capped by max_discount_inr and price."""
    if promo is None:
        return 0
    if promo.discount_type in ("fixed", "fixed_amount") and promo.discount_value:
        discount = int(promo.discount_value)
    else:
        percent = promo.discount_percent or promo.discount_value or 0
        discount = price_paise * int(percent) // 100
    if promo.max_discount_inr:
        discount = min(discount, promo.max_discount_inr)
    discount = max(0, min(discount, price_paise))
    # Keep the final charge a whole-rupee amount so the UI, the payment record
    # and the gateway all show the same number (no ₹499.50 vs ₹500 drift).
    discount += (price_paise - discount) % 100
    return discount


def create_subscription(db: "DbSession", user: "User", plan_id: str, promo_code: Optional[str] = None) -> dict:
    """
    Create a Razorpay subscription for the given user and plan.
    Returns a dict with razorpay_subscription_id and key_id for the frontend.

    In sandbox mode (no credentials) returns a fake ID so UI can be tested.
    """
    from app.models import Plan, Subscription, SubscriptionStatus

    if plan_id not in ("starter", "pro"):
        raise AppError("VALIDATION_ERROR", "Only 'starter' and 'pro' plans require payment.", 400)

    plan = get_plan(db, plan_id)

    # Promo is resolved BEFORE any charge path so the discounted price is the
    # one actually charged/recorded — never the original plan price.
    promo = _get_valid_promo(db, promo_code, plan_id=plan.id) if promo_code else None
    discount_paise = compute_promo_discount(promo, plan.price_inr)
    charge_paise = plan.price_inr - discount_paise

    if _is_sandbox():
        # Sandbox / demo mode: return a fake subscription so UI is testable.
        logger.warning("Razorpay sandbox mode: returning fake subscription ID.")
        fake_sub_id = f"sub_SANDBOX_{user.id[:8]}"
        sub_row = _upsert_subscription_row(
            db, user=user, plan=plan,
            razorpay_sub_id=fake_sub_id,
            status=SubscriptionStatus.active,
        )
        _apply_plan_to_user(db, user=user, plan=plan)
        # Record a synthetic captured payment so the admin billing view has data.
        _record_payment(
            db,
            user_id=user.id,
            subscription_id=sub_row.id,
            plan_id=plan.id,
            razorpay_payment_id=f"pay_SANDBOX_{user.id[:8]}",
            amount_inr=charge_paise,
            discount_inr=discount_paise,
            promo_code=promo.code if promo else None,
            status="captured",
            method="sandbox",
            description=f"Sandbox subscription — {plan.name}",
        )
        if promo is not None:
            promo.times_redeemed = (promo.times_redeemed or 0) + 1
        return {
            "razorpay_subscription_id": fake_sub_id,
            "razorpay_key_id": "rzp_test_sandbox",
            "plan_name": plan.name,
            "amount_inr": charge_paise // 100,
        }

    if not plan.razorpay_plan_id:
        raise AppError(
            "PAYMENT_NOT_CONFIGURED",
            f"Razorpay plan ID for '{plan_id}' is not configured. "
            "Set VWA_RAZORPAY_PLAN_ID_STARTER / VWA_RAZORPAY_PLAN_ID_PRO in .env.",
            503,
        )

    # Live mode: Razorpay applies discounts via Offers. If the promo has no
    # offer configured we must FAIL, not silently charge full price.
    offer_id = None
    if promo is not None:
        if not promo.razorpay_offer_id:
            raise AppError(
                "PROMO_NOT_CONFIGURED",
                "This promo code is not configured for live payments yet. "
                "Remove the code to continue at the standard price.",
                409,
            )
        offer_id = promo.razorpay_offer_id

    client = _razorpay_client()
    try:
        sub_payload = {
            "plan_id": plan.razorpay_plan_id,
            "total_count": 12,          # 12 months; auto-renews until cancelled
            "quantity": 1,
            "customer_notify": 1,
            "notes": {
                "user_id": user.id,
                "plan_id": plan.id,
                "email": user.email,
            },
        }
        if offer_id:
            sub_payload["offer_id"] = offer_id
            
        sub = client.subscription.create(sub_payload)
    except Exception as exc:
        logger.error("Razorpay create subscription failed: %s", exc)
        raise AppError("PAYMENT_ERROR", f"Could not create subscription: {exc}", 502)

    _upsert_subscription_row(
        db, user=user, plan=plan,
        razorpay_sub_id=sub["id"],
        # Creating a Razorpay subscription does not mean the customer has
        # authorised or paid it. The webhook promotes it to active only after
        # Razorpay confirms the subscription/payment.
        status=SubscriptionStatus.pending,
    )
    if promo is not None:
        promo.times_redeemed = (promo.times_redeemed or 0) + 1

    return {
        "razorpay_subscription_id": sub["id"],
        "razorpay_key_id": settings.razorpay_key_id,
        "plan_name": plan.name,
        "amount_inr": charge_paise // 100,
    }


def cancel_subscription(db: "DbSession", user: "User") -> None:
    """Cancel the user's active Razorpay subscription at period end."""
    from app.models import Subscription, SubscriptionStatus

    sub = user.subscription
    if sub is None or sub.status == SubscriptionStatus.cancelled:
        raise AppError("NOT_FOUND", "No active subscription to cancel.", 404)

    if not _is_sandbox():
        client = _razorpay_client()
        try:
            # cancel_at_cycle_end=1 means it stays active until period ends
            client.subscription.cancel(
                sub.razorpay_subscription_id,
                {"cancel_at_cycle_end": 1},
            )
        except Exception as exc:
            logger.error("Razorpay cancel subscription failed: %s", exc)
            raise AppError("PAYMENT_ERROR", f"Could not cancel subscription: {exc}", 502)

    sub.status = SubscriptionStatus.cancelled
    sub.cancelled_at = datetime.now(timezone.utc)
    db.flush()


def _upsert_subscription_row(
    db: "DbSession",
    *,
    user: "User",
    plan: "Plan",
    razorpay_sub_id: str,
    status: "SubscriptionStatus",
    payment_id: Optional[str] = None,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
) -> "Subscription":
    from app.models import Subscription, SubscriptionStatus

    sub = user.subscription
    if sub is None:
        sub = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            razorpay_subscription_id=razorpay_sub_id,
            status=status,
        )
        db.add(sub)
    else:
        sub.plan_id = plan.id
        sub.razorpay_subscription_id = razorpay_sub_id
        sub.status = status

    if payment_id:
        sub.razorpay_payment_id = payment_id
    if period_start:
        sub.current_period_start = period_start
    if period_end:
        sub.current_period_end = period_end

    db.flush()
    return sub


def _apply_plan_to_user(db: "DbSession", *, user: "User", plan: "Plan") -> None:
    """Upgrade the user row to the given plan and top up daily credits."""
    user.plan_id = plan.id
    user.credits_remaining = plan.credits_per_day
    _upsert_credit_ledger(db, user=user, plan=plan)
    db.flush()


def _upsert_credit_ledger(db: "DbSession", *, user: "User", plan: "Plan") -> None:
    from app.models import CreditLedger

    ledger = user.credit_ledger
    now = datetime.now(timezone.utc)
    if ledger is None:
        ledger = CreditLedger(
            user_id=user.id,
            credits_limit=plan.credits_per_day,
            credits_used_today=0,
            last_reset_at=now,
        )
        db.add(ledger)
    else:
        ledger.credits_limit = plan.credits_per_day
        ledger.credits_used_today = 0
        ledger.last_reset_at = now
    db.flush()


# ---------------------------------------------------------------------------
# Webhook processing
# ---------------------------------------------------------------------------

def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify Razorpay webhook HMAC-SHA256 signature.

    The unsigned path is allowed ONLY in sandbox mode (no Razorpay keys at
    all). With live keys configured, a missing webhook secret must reject
    every request — otherwise anyone who can reach /payments/webhook can
    forge a subscription.activated payload and grant themselves a paid plan.
    """
    if not settings.razorpay_webhook_secret:
        if _is_sandbox():
            logger.warning("Webhook secret not configured; skipping signature check (sandbox).")
            return True
        logger.error(
            "RAZORPAY_WEBHOOK_SECRET is not set but live Razorpay keys are configured — "
            "rejecting webhook. Set the secret from the Razorpay dashboard."
        )
        return False
    if not signature:
        return False
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def handle_webhook(db: "DbSession", event: str, payload: dict) -> str:
    """Process a verified Razorpay webhook event.

    Returns a human-readable description of what was done.
    """
    from app.models import Plan, Subscription, SubscriptionStatus

    logger.info("Razorpay webhook: %s", event)

    if event == "subscription.activated":
        return _handle_subscription_activated(db, payload)
    elif event in ("subscription.cancelled", "subscription.completed"):
        return _handle_subscription_cancelled(db, payload)
    elif event == "subscription.charged":
        # Renewal payment — top up credits for another month
        return _handle_subscription_charged(db, payload)
    elif event == "payment.failed":
        return _handle_payment_failed(db, payload)
    else:
        logger.debug("Unhandled webhook event: %s", event)
        return f"Event '{event}' acknowledged but not handled."


def _get_sub_entity(payload: dict) -> dict:
    return payload.get("subscription", {}).get("entity", {})


def _get_payment_entity(payload: dict) -> dict:
    return payload.get("payment", {}).get("entity", {})


def _handle_subscription_activated(db: "DbSession", payload: dict) -> str:
    from app.models import Plan, Subscription, SubscriptionStatus, User

    sub_entity = _get_sub_entity(payload)
    razorpay_sub_id = sub_entity.get("id")
    notes = sub_entity.get("notes", {})
    user_id = notes.get("user_id")
    plan_id = notes.get("plan_id")

    if not razorpay_sub_id or not user_id:
        logger.error("subscription.activated missing sub ID or user ID: %s", payload)
        return "Missing data in webhook payload."

    user = db.get(User, user_id)
    if user is None:
        logger.error("subscription.activated: user %s not found", user_id)
        return f"User {user_id} not found."

    plan = db.get(Plan, plan_id or "starter")
    if plan is None:
        return f"Plan {plan_id} not found."

    _upsert_subscription_row(
        db, user=user, plan=plan,
        razorpay_sub_id=razorpay_sub_id,
        status=SubscriptionStatus.active,
    )
    _apply_plan_to_user(db, user=user, plan=plan)
    return f"Activated {plan.name} plan for user {user.email}."


def _handle_subscription_cancelled(db: "DbSession", payload: dict) -> str:
    from app.models import Plan, Subscription, SubscriptionStatus, User

    sub_entity = _get_sub_entity(payload)
    razorpay_sub_id = sub_entity.get("id")
    if not razorpay_sub_id:
        return "Missing subscription ID."

    sub: Subscription | None = (
        db.query(Subscription)
        .filter(Subscription.razorpay_subscription_id == razorpay_sub_id)
        .first()
    )
    if sub is None:
        return f"Subscription {razorpay_sub_id} not found locally."

    sub.status = SubscriptionStatus.cancelled
    sub.cancelled_at = datetime.now(timezone.utc)

    user = db.get(User, sub.user_id)
    if user:
        free_plan = db.get(Plan, "free")
        if free_plan:
            user.plan_id = free_plan.id
            user.credits_remaining = free_plan.credits_per_day
    db.flush()
    return f"Subscription {razorpay_sub_id} cancelled; user reverted to Free."


def _handle_subscription_charged(db: "DbSession", payload: dict) -> str:
    from app.models import Plan, Subscription, User

    sub_entity = _get_sub_entity(payload)
    razorpay_sub_id = sub_entity.get("id")
    sub: Subscription | None = (
        db.query(Subscription)
        .filter(Subscription.razorpay_subscription_id == razorpay_sub_id)
        .first()
    )
    if sub is None:
        return f"Subscription {razorpay_sub_id} not found."

    user = db.get(User, sub.user_id)
    plan = db.get(Plan, sub.plan_id)
    if user and plan:
        _apply_plan_to_user(db, user=user, plan=plan)
        # PRD §13: record the captured renewal payment. Use the actual charged
        # amount; if it differs from the plan price (e.g. an offer/promo), keep
        # the real number and flag review only when the amount is missing.
        payment_entity = _get_payment_entity(payload)
        raw_amount = payment_entity.get("amount")
        _record_payment(
            db,
            user_id=user.id,
            subscription_id=sub.id,
            plan_id=plan.id,
            razorpay_payment_id=payment_entity.get("id"),
            amount_inr=int(raw_amount) if raw_amount else plan.price_inr,
            manual_review=raw_amount is None,
            status="captured",
            method=payment_entity.get("method"),
            description=f"Subscription renewal — {plan.name}",
        )
    return f"Renewed credits for subscription {razorpay_sub_id}."


def _handle_payment_failed(db: "DbSession", payload: dict) -> str:
    from app.models import User

    payment_entity = _get_payment_entity(payload)
    logger.warning("Payment failed: %s", payment_entity.get("id"))
    # Best-effort failed-payment record (PRD §13.3) when we can tie it to a user.
    user_id = (payment_entity.get("notes") or {}).get("user_id")
    if user_id and db.get(User, user_id) is not None:
        _record_payment(
            db,
            user_id=user_id,
            razorpay_payment_id=payment_entity.get("id"),
            amount_inr=int(payment_entity.get("amount") or 0),
            status="failed",
            method=payment_entity.get("method"),
            description=payment_entity.get("error_description") or "Payment failed",
        )
    return f"Payment failed: {payment_entity.get('id')}."


def _record_payment(db: "DbSession", **fields) -> None:
    """Best-effort payments-history insert; ignores duplicate razorpay ids so
    webhook retries stay idempotent."""
    try:
        from app.models import Payment
        rp_id = fields.get("razorpay_payment_id")
        if rp_id and db.query(Payment).filter(Payment.razorpay_payment_id == rp_id).first():
            return
        db.add(Payment(**fields))
        db.flush()
    except Exception as exc:  # noqa: BLE001
        logger.error("payments insert failed: %s", exc)


# ---------------------------------------------------------------------------
# Credit management
# ---------------------------------------------------------------------------

def get_credit_status(db: "DbSession", user: "User") -> dict:
    """Return current credit status for the user."""
    plan = get_user_plan_or_free(db, user)
    ledger = user.credit_ledger

    credits_used = ledger.credits_used_today if ledger else 0
    credits_remaining = user.credits_remaining

    return {
        "plan_id": plan.id,
        "plan_name": plan.name,
        "credits_per_day": plan.credits_per_day,
        "credits_remaining": credits_remaining,
        "credits_used_today": credits_used,
    }


def deduct_credits(
    db: "DbSession", user: "User", cost: int = CREDITS_PER_JOB,
    *, project_id: Optional[str] = None, job_id: Optional[str] = None,
) -> None:
    """Deduct credits from the user's balance.

    Raises AppError 402 if the user has insufficient credits. Writes an
    immutable credit_transactions row (PRD §17.2, source='job').

    The user row is locked (SELECT ... FOR UPDATE; a no-op on SQLite) and its
    balance re-read under the lock so two concurrent deductions cannot both
    pass the balance check and last-write-win each other.
    """
    user_cls = type(user)
    db.query(user_cls).filter(user_cls.id == user.id).with_for_update().populate_existing().one()
    if user.credits_remaining < cost:
        raise AppError(
            "INSUFFICIENT_CREDITS",
            f"You need {cost} credits but only have {user.credits_remaining} remaining today. "
            "Wait for the daily reset or upgrade your plan.",
            402,
        )
    before = user.credits_remaining
    user.credits_remaining -= cost
    if user.credit_ledger:
        user.credit_ledger.credits_used_today += cost
    _record_credit_txn(
        db, user_id=user.id, amount=cost, direction="debit",
        balance_before=before, balance_after=user.credits_remaining,
        source="job", reason="Job credit deduction",
        project_id=project_id, job_id=job_id,
    )
    db.flush()


def refund_credits(
    db: "DbSession", user: "User", cost: int = CREDITS_PER_JOB,
    *, project_id: Optional[str] = None, job_id: Optional[str] = None,
) -> None:
    """Return credits when a job fails before processing begins."""
    plan = get_user_plan_or_free(db, user)
    user_cls = type(user)
    db.query(user_cls).filter(user_cls.id == user.id).with_for_update().populate_existing().one()
    before = user.credits_remaining
    user.credits_remaining = min(user.credits_remaining + cost, plan.credits_per_day)
    if user.credit_ledger:
        user.credit_ledger.credits_used_today = max(
            0, user.credit_ledger.credits_used_today - cost
        )
    if user.credits_remaining != before:
        _record_credit_txn(
            db, user_id=user.id, amount=user.credits_remaining - before, direction="credit",
            balance_before=before, balance_after=user.credits_remaining,
            source="refund", reason="Failed-job credit refund",
            project_id=project_id, job_id=job_id,
        )
    db.flush()


def _record_credit_txn(db: "DbSession", **fields) -> None:
    """Best-effort immutable ledger insert. Never blocks the credit path —
    a ledger failure logs instead of failing the user-facing operation."""
    try:
        from app.models import CreditTransaction
        db.add(CreditTransaction(**fields))
    except Exception as exc:  # noqa: BLE001
        logger.error("credit_transactions insert failed: %s", exc)


def reset_daily_credits(db: "DbSession") -> int:
    """Reset credits for all users. Called daily by the Celery beat task.

    Returns the number of users whose credits were reset.
    """
    from sqlalchemy import text

    now = datetime.now(timezone.utc)
    # Reset users.credits_remaining to their plan's credits_per_day
    result = db.execute(text("""
        UPDATE users u
        SET credits_remaining = COALESCE(p.credits_per_day, 500),
            updated_at = :now
        FROM plans p
        WHERE u.plan_id = p.id
           OR (u.plan_id IS NULL AND p.id = 'free')
    """), {"now": now})

    # Reset the ledger
    db.execute(text("""
        UPDATE credit_ledger
        SET credits_used_today = 0,
            last_reset_at = :now,
            updated_at = :now
    """), {"now": now})

    db.commit()
    return result.rowcount


__all__ = [
    "CREDITS_PER_JOB",
    "seed_plans",
    "get_plan",
    "get_user_plan_or_free",
    "create_subscription",
    "cancel_subscription",
    "verify_webhook_signature",
    "handle_webhook",
    "get_credit_status",
    "deduct_credits",
    "refund_credits",
    "reset_daily_credits",
]
