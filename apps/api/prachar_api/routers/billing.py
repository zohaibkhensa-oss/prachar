"""Billing & payments router — Stripe + Razorpay integration.

Endpoints:
  GET  /billing/plans            — list all plans with pricing & deliverables
  GET  /billing/subscription     — current tenant's subscription status
  POST /billing/checkout         — create a checkout session (Stripe or Razorpay)
  POST /billing/webhook/stripe   — Stripe webhook receiver
  POST /billing/webhook/razorpay — Razorpay webhook receiver
  POST /billing/cancel           — cancel subscription at period end
  GET  /billing/usage            — current month usage vs limits

All pricing is read from prachar_shared.plans (env-driven). No hardcoded values.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep, get_tenant_plan
from ..models import Billing, Tenant
from ..models.enums import BillingProvider, BillingStatus
from prachar_shared.config import get_settings
from prachar_shared.plans import get_plan, get_plans, list_plans, PlanSpec

router = APIRouter(prefix="/billing", tags=["billing"])
log = logging.getLogger(__name__)


# ─── Response models ────────────────────────────────────────────────────────

class PlanOut(BaseModel):
    key: str
    name: str
    tagline: str
    price_inr: int
    price_usd: int
    currency_inr: str
    currency_usd: str
    popular: bool
    brands_limit: int
    videos_per_month: int
    images_per_month: int
    platforms_limit: int
    weekly_loop: bool
    google_ads: bool
    meta_ads: bool
    white_label: bool
    api_access: bool
    priority_support: bool
    ai_budget_inr: int
    video_quality_tier: str
    accent: str
    icon: str
    deliverables: list[dict[str, Any]]


class PlansResponse(BaseModel):
    plans: list[PlanOut]
    currency: str  # tenant's preferred currency (INR for India, USD otherwise)


class SubscriptionOut(BaseModel):
    plan: str
    status: str
    provider: str | None
    sub_id: str | None
    current_period_end: str | None = None
    cancel_at_period_end: bool = False


class CheckoutRequest(BaseModel):
    plan: str  # starter | growth | agency
    provider: str  # stripe | razorpay
    success_url: str = ""
    cancel_url: str = ""


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    provider: str
    plan: str
    amount_inr: int
    amount_usd: int


class UsageOut(BaseModel):
    plan: str
    ai_tokens_used: int
    ai_budget: int
    videos_used: int
    videos_limit: int
    images_used: int
    images_limit: int
    brands_count: int
    brands_limit: int


# ─── Helpers ────────────────────────────────────────────────────────────────

def _settings():
    return get_settings()


def _plan_to_out(p: PlanSpec) -> PlanOut:
    return PlanOut(**p.to_dict())


def _tenant_currency(user: CurrentUser) -> str:
    """Pick currency based on tenant locale. Default INR for India."""
    # Could be extended to read from Tenant.locale once that field exists.
    return "INR"


async def _get_billing(session: SessionDep, tenant_id: uuid.UUID) -> Billing | None:
    res = await session.execute(select(Billing).where(Billing.tenant_id == tenant_id))
    return res.scalar_one_or_none()


# ─── Plans endpoint ─────────────────────────────────────────────────────────

@router.get("/plans", response_model=PlansResponse)
async def get_plans_endpoint(user: CurrentUser) -> PlansResponse:
    """List all subscription plans with pricing and deliverables.

    No hardcoded values — all pricing comes from prachar_shared.plans which
    reads from env-driven Settings.
    """
    plans = [_plan_to_out(p) for p in list_plans()]
    currency = _tenant_currency(user)
    return PlansResponse(plans=plans, currency=currency)


# ─── Subscription status ────────────────────────────────────────────────────

@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(
    user: CurrentUser,
    session: SessionDep,
) -> SubscriptionOut:
    """Get the current tenant's subscription status."""
    plan = await get_tenant_plan(session, user)
    billing = await _get_billing(session, user.tenant_id)
    if not billing:
        return SubscriptionOut(
            plan=plan,
            status=BillingStatus.trialing.value,
            provider=None,
            sub_id=None,
        )
    return SubscriptionOut(
        plan=plan,
        status=billing.status.value if hasattr(billing.status, "value") else str(billing.status),
        provider=billing.provider.value if hasattr(billing.provider, "value") else str(billing.provider),
        sub_id=billing.sub_id,
        cancel_at_period_end=False,  # would come from provider API in production
    )


# ─── Checkout ───────────────────────────────────────────────────────────────

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    req: CheckoutRequest,
    user: CurrentUser,
    session: SessionDep,
) -> CheckoutResponse:
    """Create a checkout session for a plan via Stripe or Razorpay.

    The provider handles the actual payment UI. We just create the session
    and return the URL the frontend should redirect to.
    """
    plan = get_plan(req.plan)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {req.plan}")

    s = _settings()
    base_url = s.next_public_api_base or "http://localhost:8000"
    success_url = req.success_url or f"{base_url}/app/settings?billing=success"
    cancel_url = req.cancel_url or f"{base_url}/app/settings?billing=cancelled"

    if req.provider == "stripe":
        return await _stripe_checkout(plan, success_url, cancel_url, user)
    elif req.provider == "razorpay":
        return await _razorpay_checkout(plan, success_url, cancel_url, user, session)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}. Use 'stripe' or 'razorpay'.")


async def _stripe_checkout(
    plan: PlanSpec,
    success_url: str,
    cancel_url: str,
    user: CurrentUser,
) -> CheckoutResponse:
    """Create a Stripe Checkout session for a subscription."""
    s = _settings()
    if not s.stripe_api_key:
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured. Set STRIPE_API_KEY in .env",
        )
    import stripe
    stripe.api_key = s.stripe_api_key

    # Use pre-created Stripe price IDs if configured, otherwise create on the fly
    price_id_map = {
        "starter": s.stripe_price_starter_id,
        "growth": s.stripe_price_growth_id,
        "agency": s.stripe_price_agency_id,
    }
    price_id = price_id_map.get(plan.key, "")

    try:
        if price_id:
            # Use existing price (production path)
            checkout_session = stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=str(user.tenant_id),
                metadata={"plan": plan.key, "tenant_id": str(user.tenant_id)},
            )
        else:
            # Create inline price (dev/test path — uses USD cents)
            checkout_session = stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"PRACHAR {plan.name} (monthly)"},
                        "unit_amount": plan.price_usd * 100,  # cents
                        "recurring": {"interval": "month"},
                    },
                    "quantity": 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=str(user.tenant_id),
                metadata={"plan": plan.key, "tenant_id": str(user.tenant_id)},
            )
    except Exception as e:
        log.error("Stripe checkout failed: %s", str(e)[:300])
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)[:200]}")

    return CheckoutResponse(
        checkout_url=checkout_session.url,
        session_id=checkout_session.id,
        provider="stripe",
        plan=plan.key,
        amount_inr=plan.price_inr,
        amount_usd=plan.price_usd,
    )


async def _razorpay_checkout(
    plan: PlanSpec,
    success_url: str,
    cancel_url: str,
    user: CurrentUser,
    session: SessionDep,
) -> CheckoutResponse:
    """Create a Razorpay subscription or one-time payment link."""
    s = _settings()
    if not s.razorpay_key_id or not s.razorpay_key_secret:
        raise HTTPException(
            status_code=503,
            detail="Razorpay not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env",
        )
    import razorpay

    client = razorpay.Client(auth=(s.razorpay_key_id, s.razorpay_key_secret))

    # Use pre-created Razorpay plan IDs if configured, otherwise create a
    # subscription with inline amount (in paise).
    plan_id_map = {
        "starter": s.razorpay_plan_starter_id,
        "growth": s.razorpay_plan_growth_id,
        "agency": s.razorpay_plan_agency_id,
    }
    razorpay_plan_id = plan_id_map.get(plan.key, "")

    try:
        if razorpay_plan_id:
            # Use existing Razorpay plan (production path)
            sub = client.subscription.create({
                "plan_id": razorpay_plan_id,
                "total_count": 12,  # 12 months
                "customer_notify": 1,
                "notify_info": {"notify_email": user.email if hasattr(user, "email") else ""},
                "notes": {
                    "plan": plan.key,
                    "tenant_id": str(user.tenant_id),
                },
            })
            checkout_url = sub.get("short_url", "")
            session_id = sub.get("id", "")
        else:
            # Create a one-time payment link (dev/test path — uses INR paise)
            amount_paise = plan.price_inr * 100
            link = client.payment_link.create({
                "amount": amount_paise,
                "currency": "INR",
                "description": f"PRACHAR {plan.name} — monthly subscription",
                "callback_url": success_url,
                "callback_method": "get",
                "notes": {
                    "plan": plan.key,
                    "tenant_id": str(user.tenant_id),
                },
            })
            checkout_url = link.get("short_url", "")
            session_id = link.get("id", "")
    except Exception as e:
        log.error("Razorpay checkout failed: %s", str(e)[:300])
        raise HTTPException(status_code=502, detail=f"Razorpay error: {str(e)[:200]}")

    return CheckoutResponse(
        checkout_url=checkout_url,
        session_id=session_id,
        provider="razorpay",
        plan=plan.key,
        amount_inr=plan.price_inr,
        amount_usd=plan.price_usd,
    )


# ─── Webhooks ───────────────────────────────────────────────────────────────

@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    session: SessionDep,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    """Handle Stripe webhook events.

    Verifies the signature using STRIPE_WEBHOOK_SECRET, then updates the
    tenant's Billing row based on the event type.
    """
    s = _settings()
    if not s.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="STRIPE_WEBHOOK_SECRET not configured")

    payload = await request.body()
    import stripe
    stripe.api_key = s.stripe_api_key

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature or "",
            secret=s.stripe_webhook_secret,
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)[:200]}")

    return await _handle_stripe_event(event, session)


async def _handle_stripe_event(event: Any, session: SessionDep) -> dict:
    """Process a verified Stripe event and update billing state."""
    etype = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if etype == "checkout.session.completed":
        tenant_id = data.get("client_reference_id")
        sub_id = data.get("subscription")
        plan_key = data.get("metadata", {}).get("plan", "starter")
        if tenant_id:
            await _update_billing(session, uuid.UUID(tenant_id), BillingProvider.stripe, sub_id, BillingStatus.active, plan_key)
        return {"status": "ok", "action": "subscription_activated"}

    elif etype == "customer.subscription.deleted":
        sub_id = data.get("id")
        await _cancel_billing_by_sub(session, sub_id)
        return {"status": "ok", "action": "subscription_canceled"}

    elif etype == "invoice.payment_failed":
        sub_id = data.get("subscription")
        await _mark_past_due(session, sub_id)
        return {"status": "ok", "action": "marked_past_due"}

    # Unhandled events are acknowledged but not processed
    return {"status": "ok", "action": "ignored", "type": etype}


@router.post("/webhook/razorpay")
async def razorpay_webhook(
    request: Request,
    session: SessionDep,
    x_razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
):
    """Handle Razorpay webhook events.

    Verifies the signature using RAZORPAY_WEBHOOK_SECRET, then updates the
    tenant's Billing row.
    """
    s = _settings()
    if not s.razorpay_webhook_secret:
        raise HTTPException(status_code=503, detail="RAZORPAY_WEBHOOK_SECRET not configured")

    payload = await request.body()
    expected_sig = hmac.new(
        s.razorpay_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, x_razorpay_signature or ""):
        raise HTTPException(status_code=400, detail="Invalid Razorpay signature")

    try:
        body = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = body.get("event", "")
    payload_data = body.get("payload", {})

    if event == "subscription.activated":
        sub = payload_data.get("subscription", {}).get("entity", {})
        sub_id = sub.get("id")
        notes = sub.get("notes", {})
        tenant_id = notes.get("tenant_id")
        plan_key = notes.get("plan", "starter")
        if tenant_id:
            await _update_billing(session, uuid.UUID(tenant_id), BillingProvider.razorpay, sub_id, BillingStatus.active, plan_key)
        return {"status": "ok", "action": "subscription_activated"}

    elif event == "subscription.cancelled":
        sub_id = payload_data.get("subscription", {}).get("entity", {}).get("id")
        await _cancel_billing_by_sub(session, sub_id)
        return {"status": "ok", "action": "subscription_canceled"}

    elif event == "subscription.charged":
        # Successful recurring payment — ensure active
        sub = payload_data.get("subscription", {}).get("entity", {})
        sub_id = sub.get("id")
        notes = sub.get("notes", {})
        tenant_id = notes.get("tenant_id")
        if tenant_id:
            await _update_billing(session, uuid.UUID(tenant_id), BillingProvider.razorpay, sub_id, BillingStatus.active, notes.get("plan", "starter"))
        return {"status": "ok", "action": "payment_succeeded"}

    elif event == "payment.failed":
        # Could mark past_due if we can find the subscription
        return {"status": "ok", "action": "payment_failed_ignored"}

    return {"status": "ok", "action": "ignored", "event": event}


# ─── Cancel ─────────────────────────────────────────────────────────────────

@router.post("/cancel")
async def cancel_subscription(
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Cancel the current subscription at the end of the billing period."""
    billing = await _get_billing(session, user.tenant_id)
    if not billing or not billing.sub_id:
        raise HTTPException(status_code=400, detail="No active subscription to cancel")

    s = _settings()
    provider = billing.provider.value if hasattr(billing.provider, "value") else str(billing.provider)

    try:
        if provider == "stripe":
            import stripe
            stripe.api_key = s.stripe_api_key
            stripe.Subscription.modify(billing.sub_id, cancel_at_period_end=True)
        elif provider == "razorpay":
            import razorpay
            client = razorpay.Client(auth=(s.razorpay_key_id, s.razorpay_key_secret))
            client.subscription.cancel(billing.sub_id, cancel_at_period_end=True)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    except HTTPException:
        raise
    except Exception as e:
        log.error("Cancel failed: %s", str(e)[:200])
        raise HTTPException(status_code=502, detail=f"Cancel failed: {str(e)[:200]}")

    return {"status": "ok", "message": "Subscription will cancel at end of billing period"}


# ─── Usage ──────────────────────────────────────────────────────────────────

@router.get("/usage", response_model=UsageOut)
async def get_usage(
    user: CurrentUser,
    session: SessionDep,
) -> UsageOut:
    """Get current month usage vs plan limits."""
    plan_key = await get_tenant_plan(session, user)
    plan = get_plan(plan_key) or get_plan("starter")
    billing = await _get_billing(session, user.tenant_id)

    # Count brands for this tenant
    from ..models import Brand
    res = await session.execute(
        select(Brand).where(Brand.tenant_id == user.tenant_id)
    )
    brands_count = len(res.scalars().all())

    return UsageOut(
        plan=plan_key,
        ai_tokens_used=billing.ai_tokens_used_month if billing else 0,
        ai_budget=billing.ai_budget_month if billing else plan.ai_budget_inr,
        videos_used=0,  # would track from video_gen audit events
        videos_limit=plan.videos_per_month,
        images_used=0,
        images_limit=plan.images_per_month,
        brands_count=brands_count,
        brands_limit=plan.brands_limit,
    )


# ─── Internal helpers ───────────────────────────────────────────────────────

async def _update_billing(
    session: SessionDep,
    tenant_id: uuid.UUID,
    provider: BillingProvider,
    sub_id: str | None,
    status: BillingStatus,
    plan_key: str,
) -> None:
    """Update or create the billing row and bump the tenant's plan."""
    billing = await _get_billing(session, tenant_id)
    if billing:
        billing.provider = provider
        billing.sub_id = sub_id
        billing.status = status
    else:
        billing = Billing(
            tenant_id=tenant_id,
            provider=provider,
            sub_id=sub_id,
            status=status,
            ai_budget_month=get_plan(plan_key).ai_budget_inr if get_plan(plan_key) else 0,
        )
        session.add(billing)

    # Update tenant plan
    res = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = res.scalar_one_or_none()
    if tenant:
        tenant.plan = plan_key

    await session.commit()
    log.info("Billing updated: tenant=%s plan=%s provider=%s status=%s", tenant_id, plan_key, provider, status)


async def _cancel_billing_by_sub(session: SessionDep, sub_id: str | None) -> None:
    if not sub_id:
        return
    res = await session.execute(select(Billing).where(Billing.sub_id == sub_id))
    billing = res.scalar_one_or_none()
    if billing:
        billing.status = BillingStatus.canceled
        await session.commit()


async def _mark_past_due(session: SessionDep, sub_id: str | None) -> None:
    if not sub_id:
        return
    res = await session.execute(select(Billing).where(Billing.sub_id == sub_id))
    billing = res.scalar_one_or_none()
    if billing:
        billing.status = BillingStatus.past_due
        await session.commit()


# ─── Invoicing (GST-compliant for India) ──────────────────────────────────────

class InvoiceOut(BaseModel):
    id: str
    tenant_id: str
    plan: str
    amount_inr: int
    gst_inr: int
    total_inr: int
    currency: str
    status: str
    created_at: str
    invoice_number: str
    gstin: str | None = None


class InvoicesResponse(BaseModel):
    invoices: list[InvoiceOut]


@router.get("/invoices", response_model=InvoicesResponse)
async def list_invoices(
    user: CurrentUser,
    session: SessionDep,
) -> InvoicesResponse:
    """List invoices for the current tenant.

    In production, this fetches from Stripe/Razorpay. For now, returns
    a computed list from billing history. GST (18%) is included for India.
    """
    billing = await _get_billing(session, user.tenant_id)
    if not billing or not billing.sub_id:
        return InvoicesResponse(invoices=[])

    s = _settings()
    plan_key = await get_tenant_plan(session, user)
    plan = get_plan(plan_key) or get_plan("starter")

    # GST calculation (18% on plan price for India)
    base_amount = plan.price_inr
    gst_amount = int(base_amount * 0.18)
    total = base_amount + gst_amount

    # Generate a sequential invoice number
    import datetime
    now = datetime.datetime.now(datetime.UTC)
    invoice_number = f"INV-{now.strftime('%Y%m')}-{str(user.tenant_id)[:8].upper()}"

    invoice = InvoiceOut(
        id=str(uuid.uuid4()),
        tenant_id=str(user.tenant_id),
        plan=plan_key,
        amount_inr=base_amount,
        gst_inr=gst_amount,
        total_inr=total,
        currency="INR",
        status=billing.status.value if hasattr(billing.status, "value") else str(billing.status),
        created_at=now.isoformat(),
        invoice_number=invoice_number,
    )

    return InvoicesResponse(invoices=[invoice])


# ─── Coupons ──────────────────────────────────────────────────────────────────

class CouponValidateRequest(BaseModel):
    code: str
    plan: str


class CouponValidateResponse(BaseModel):
    valid: bool
    code: str
    discount_pct: int = 0
    discount_amount: int = 0
    message: str = ""


# Simple in-memory coupon store. In production, store in DB.
_COUPONS: dict[str, dict] = {
    "LAUNCH50": {"discount_pct": 50, "plans": ["starter", "growth", "agency"], "max_uses": 100, "uses": 0},
    "EARLYBIRD25": {"discount_pct": 25, "plans": ["starter", "growth"], "max_uses": 200, "uses": 0},
    "AGENCY20": {"discount_pct": 20, "plans": ["agency"], "max_uses": 50, "uses": 0},
}


@router.post("/coupons/validate", response_model=CouponValidateResponse)
async def validate_coupon(
    req: CouponValidateRequest,
    user: CurrentUser,
) -> CouponValidateResponse:
    """Validate a coupon code for a given plan.

    Returns the discount percentage and amount if valid.
    """
    code = req.code.upper().strip()
    coupon = _COUPONS.get(code)

    if not coupon:
        return CouponValidateResponse(valid=False, code=code, message="Invalid coupon code")

    if req.plan not in coupon["plans"]:
        return CouponValidateResponse(valid=False, code=code, message=f"Coupon not valid for {req.plan} plan")

    if coupon["uses"] >= coupon["max_uses"]:
        return CouponValidateResponse(valid=False, code=code, message="Coupon usage limit reached")

    plan = get_plan(req.plan)
    if not plan:
        return CouponValidateResponse(valid=False, code=code, message="Invalid plan")

    discount_amount = int(plan.price_inr * (coupon["discount_pct"] / 100))

    return CouponValidateResponse(
        valid=True,
        code=code,
        discount_pct=coupon["discount_pct"],
        discount_amount=discount_amount,
        message=f"{coupon['discount_pct']}% off applied",
    )
