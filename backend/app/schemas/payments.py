"""Pydantic schemas for the payment / billing endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Inbound ---


class SubscribeRequest(BaseModel):
    """Body for POST /payments/subscribe."""
    plan_id: str  # 'starter' | 'pro'
    promo_code: Optional[str] = None


class PromoValidateRequest(BaseModel):
    code: str
    plan_id: Optional[str] = None  # validate plan applicability when provided


class PromoValidateResponse(BaseModel):
    valid: bool
    discount_percent: Optional[int] = None
    message: Optional[str] = None
    # Authoritative server-side pricing (whole rupees) so the checkout UI shows
    # exactly what will be charged — never client-side math.
    original_amount: Optional[int] = None   # plan price before discount
    discount_amount: Optional[int] = None   # amount taken off
    final_amount: Optional[int] = None      # what the user pays


class CancelRequest(BaseModel):
    """Body for POST /payments/cancel (optional reason)."""
    reason: Optional[str] = None


# --- Outbound ---


class SubscribeResponse(BaseModel):
    """Returned to the frontend so it can open the Razorpay checkout modal."""
    razorpay_subscription_id: str
    razorpay_key_id: str
    plan_name: str
    amount_inr: int   # display only; actual charge is in Razorpay plan


class SubscriptionStatusResponse(BaseModel):
    """Current user billing status."""
    plan_id: str
    plan_name: str
    credits_per_day: int
    credits_remaining: int
    subscription_status: Optional[str] = None          # active | past_due | cancelled | None
    razorpay_subscription_id: Optional[str] = None
    current_period_end: Optional[datetime] = None
    is_free: bool


class CreditStatusResponse(BaseModel):
    """Lightweight credit balance — used by the dashboard widget."""
    plan_id: str
    plan_name: str
    credits_per_day: int
    credits_remaining: int
    credits_used_today: int


class CancelResponse(BaseModel):
    success: bool
    message: str


class PublicPlanOut(BaseModel):
    """Public plan catalog entry (GET /plans — unauthenticated). A trimmed
    view of the plans table: no gateway IDs or subscriber counts."""
    id: str
    name: str
    description: Optional[str] = None
    price_inr: int                     # paise
    annual_price_inr: Optional[int] = None
    currency: str = "INR"
    billing_interval: str = "monthly"
    credits_per_day: int
    monthly_credits: Optional[int] = None
    is_recommended: bool = False
    display_order: int = 0
    max_upload_mb: Optional[int] = None
    max_duration_seconds: Optional[int] = None
    max_resolution: Optional[str] = None
    concurrent_jobs: Optional[int] = None
    storage_allowance_mb: Optional[int] = None
    retention_days: Optional[int] = None
    priority_level: Optional[int] = None
    api_access: Optional[bool] = None
    support_level: Optional[str] = None

    model_config = {"from_attributes": True}


# --- Webhook bodies (Razorpay fires JSON) ---


class RazorpayWebhookPayload(BaseModel):
    """Minimal shape we care about from Razorpay webhook POST."""
    event: str                   # e.g. subscription.activated, payment.captured
    payload: dict                # raw nested object
