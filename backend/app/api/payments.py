"""Payment / billing API routes.

Routes
------
POST  /api/v1/payments/subscribe   Create a Razorpay subscription
POST  /api/v1/payments/webhook     Razorpay webhook handler (HMAC verified)
GET   /api/v1/payments/status      Current user plan + credits
POST  /api/v1/payments/cancel      Cancel active subscription
GET   /api/v1/credits              Lightweight credit balance (used by dashboard)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Body, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.core.errors import AppError
from app.models import User
from app.schemas.payments import (
    CancelRequest,
    CancelResponse,
    CreditStatusResponse,
    PromoValidateRequest,
    PromoValidateResponse,
    PublicPlanOut,
    SubscribeRequest,
    SubscribeResponse,
    SubscriptionStatusResponse,
)
from app.services import payment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

# Public plan catalog — the pricing/checkout pages read live DB data so admin
# plan edits are reflected on the website immediately (no auth required).
plans_router = APIRouter(prefix="/plans", tags=["plans"])


@plans_router.get("", response_model=list[PublicPlanOut])
def list_public_plans(db: Session = Depends(get_db)) -> list[PublicPlanOut]:
    """Active, non-archived plans ordered for display."""
    from app.models import Plan

    rows = (
        db.query(Plan)
        .filter(Plan.is_active == True, Plan.archived == False)  # noqa: E712
        .order_by(Plan.display_order, Plan.price_inr)
        .all()
    )
    return [PublicPlanOut.model_validate(p) for p in rows]


# ---------------------------------------------------------------------------
# POST /payments/promo/validate
# ---------------------------------------------------------------------------

@router.post("/promo/validate", response_model=PromoValidateResponse)
def validate_promo(
    body: PromoValidateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PromoValidateResponse:
    """Validate a promo code with the same rules the charge path enforces
    (active, date window, usage limits, plan applicability) and return the
    exact discounted price the server will charge."""
    plan_id = body.plan_id or "starter"
    try:
        promo = payment_service._get_valid_promo(db, body.code, plan_id=plan_id)
    except AppError as exc:
        return PromoValidateResponse(valid=False, message=exc.message)
    plan = payment_service.get_plan(db, plan_id)
    discount_paise = payment_service.compute_promo_discount(promo, plan.price_inr)
    return PromoValidateResponse(
        valid=True,
        discount_percent=promo.discount_percent,
        original_amount=plan.price_inr // 100,
        discount_amount=discount_paise // 100,
        final_amount=(plan.price_inr - discount_paise) // 100,
    )


# ---------------------------------------------------------------------------
# POST /payments/subscribe
# ---------------------------------------------------------------------------


@router.post("/subscribe", response_model=SubscribeResponse)
def subscribe(
    body: SubscribeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscribeResponse:
    """Create a Razorpay subscription and return the details needed for the
    frontend Checkout modal.

    In sandbox mode (no Razorpay credentials) the response contains a fake
    subscription ID so the UI flow can be tested end-to-end.
    """
    if body.plan_id not in ("starter", "pro"):
        raise AppError("VALIDATION_ERROR", "plan_id must be 'starter' or 'pro'.", 422)

    result = payment_service.create_subscription(db, user=user, plan_id=body.plan_id, promo_code=body.promo_code)
    db.commit()
    return SubscribeResponse(**result)


# ---------------------------------------------------------------------------
# POST /payments/webhook  (no auth — Razorpay calls this publicly)
# ---------------------------------------------------------------------------


@router.post("/webhook", include_in_schema=False)
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str = Header(default=""),
) -> JSONResponse:
    """Razorpay sends POST with JSON body + X-Razorpay-Signature header.

    We verify the HMAC, then dispatch to the payment service handler.
    All responses are 200 (Razorpay retries on non-2xx). Every inbound event
    is recorded as a WebhookEvent row (PRD §13.4) so admins can inspect and
    reprocess — including rejected/invalid ones.
    """
    from app.repositories.admin import insert_webhook_event

    body = await request.body()
    signature_valid = payment_service.verify_webhook_signature(body, x_razorpay_signature)

    try:
        data = await request.json()
    except Exception:
        data = None
    event = (data or {}).get("event", "")
    payload = (data or {}).get("payload", {})
    sub_ref = ((payload.get("subscription") or {}).get("entity") or {}).get("id") if isinstance(payload, dict) else None

    def _log_event(status: str, result: str) -> None:
        try:
            insert_webhook_event(
                db,
                event_type=event or "unknown",
                razorpay_event_id=request.headers.get("x-razorpay-event-id"),
                subscription_ref=sub_ref,
                signature_valid=signature_valid,
                status=status,
                result=result,
                payload=data,
            )
            db.commit()
        except Exception:  # noqa: BLE001 — the log row must never break the webhook
            db.rollback()

    if not signature_valid:
        logger.warning("Razorpay webhook: invalid signature")
        _log_event("failed", "invalid_signature")
        return JSONResponse({"ok": False, "reason": "invalid_signature"}, status_code=400)

    if data is None:
        _log_event("failed", "invalid_json")
        return JSONResponse({"ok": False, "reason": "invalid_json"}, status_code=400)

    try:
        message = payment_service.handle_webhook(db, event=event, payload=payload)
        db.commit()
        _log_event("processed", message)
        return JSONResponse({"ok": True, "message": message})
    except Exception as exc:
        logger.exception("Webhook handler error for event %s: %s", event, exc)
        db.rollback()
        _log_event("failed", str(exc))
        return JSONResponse({"ok": False, "reason": str(exc)}, status_code=200)


# ---------------------------------------------------------------------------
# GET /payments/status
# ---------------------------------------------------------------------------


@router.get("/status", response_model=SubscriptionStatusResponse)
def subscription_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SubscriptionStatusResponse:
    """Return the current user's plan, credit balance, and subscription details."""
    plan = payment_service.get_user_plan_or_free(db, user)
    sub = user.subscription

    return SubscriptionStatusResponse(
        plan_id=plan.id,
        plan_name=plan.name,
        credits_per_day=plan.credits_per_day,
        credits_remaining=user.credits_remaining,
        subscription_status=sub.status.value if sub else None,
        razorpay_subscription_id=sub.razorpay_subscription_id if sub else None,
        current_period_end=sub.current_period_end if sub else None,
        is_free=plan.id == "free",
    )


# ---------------------------------------------------------------------------
# POST /payments/cancel
# ---------------------------------------------------------------------------


@router.post("/cancel", response_model=CancelResponse)
def cancel_subscription(
    body: CancelRequest = Body(default=CancelRequest()),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CancelResponse:
    """Cancel the user's active subscription at the end of the billing period."""
    payment_service.cancel_subscription(db, user=user)
    db.commit()
    return CancelResponse(
        success=True,
        message="Your subscription has been cancelled. You will retain access until the end of the current billing period.",
    )


# ---------------------------------------------------------------------------
# GET /credits  (lightweight widget endpoint)
# ---------------------------------------------------------------------------

credits_router = APIRouter(prefix="/credits", tags=["credits"])


@credits_router.get("", response_model=CreditStatusResponse)
def get_credits(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CreditStatusResponse:
    """Return only the credit balance — used by the dashboard sidebar widget."""
    status = payment_service.get_credit_status(db, user)
    return CreditStatusResponse(**status)
