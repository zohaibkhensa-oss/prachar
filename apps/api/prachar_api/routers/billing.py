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
            # Email invoice to user
            await _email_invoice_after_payment(session, uuid.UUID(tenant_id), plan_key)
        return {"status": "ok", "action": "subscription_activated"}

    elif etype == "customer.subscription.deleted":
        sub_id = data.get("id")
        await _cancel_billing_by_sub(session, sub_id)
        return {"status": "ok", "action": "subscription_canceled"}

    elif etype == "invoice.payment_succeeded":
        # Recurring payment succeeded — email the invoice
        sub_id = data.get("subscription")
        tenant_id = data.get("customer", {}).get("id") if isinstance(data.get("customer"), dict) else None
        # Try to find tenant from subscription metadata
        plan_key = data.get("metadata", {}).get("plan", "starter")
        # Look up billing by sub_id to find tenant
        if not tenant_id:
            billing_res = await session.execute(select(Billing).where(Billing.sub_id == sub_id))
            billing = billing_res.scalar_one_or_none()
            if billing:
                tenant_id = str(billing.tenant_id)
        if tenant_id:
            await _email_invoice_after_payment(session, uuid.UUID(tenant_id), plan_key)
        return {"status": "ok", "action": "invoice_emailed"}

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
            # Email invoice to user
            await _email_invoice_after_payment(session, uuid.UUID(tenant_id), plan_key)
        return {"status": "ok", "action": "subscription_activated"}

    elif event == "subscription.cancelled":
        sub_id = payload_data.get("subscription", {}).get("entity", {}).get("id")
        await _cancel_billing_by_sub(session, sub_id)
        return {"status": "ok", "action": "subscription_canceled"}

    elif event == "subscription.charged":
        # Successful recurring payment — ensure active + email invoice
        sub = payload_data.get("subscription", {}).get("entity", {})
        sub_id = sub.get("id")
        notes = sub.get("notes", {})
        tenant_id = notes.get("tenant_id")
        plan_key = notes.get("plan", "starter")
        if tenant_id:
            await _update_billing(session, uuid.UUID(tenant_id), BillingProvider.razorpay, sub_id, BillingStatus.active, plan_key)
            # Email invoice to user
            await _email_invoice_after_payment(session, uuid.UUID(tenant_id), plan_key)
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


# ─── PDF Invoice Generation ──────────────────────────────────────────────────

def _generate_invoice_pdf(
    invoice_number: str,
    tenant_name: str,
    tenant_id_short: str,
    plan_key: str,
    base_amount: int,
    gst_amount: int,
    total: int,
    status_text: str,
    now: Any | None = None,
) -> bytes:
    """Generate a GST-compliant PDF invoice and return the bytes.

    Reusable: called from both the download endpoint and the webhook handlers
    (for emailing invoices after payment).
    """
    import io
    import datetime
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas as rl_canvas

    if now is None:
        now = datetime.datetime.now(datetime.UTC)

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # Colors
    primary = HexColor("#1a1a2e")
    accent = HexColor("#6c5ce7")
    light_gray = HexColor("#f0f0f5")
    dark_gray = HexColor("#333333")

    # ─── Header bar ───
    c.setFillColor(primary)
    c.rect(0, height - 35 * mm, width, 35 * mm, fill=1, stroke=0)

    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 24)
    c.drawString(20 * mm, height - 18 * mm, "PRACHAR")
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, height - 24 * mm, "AI-Driven Advertising Platform")
    c.drawString(20 * mm, height - 29 * mm, "hello@prachar.app | www.prachar.app")

    c.setFont("Helvetica-Bold", 16)
    c.drawRightString(width - 20 * mm, height - 18 * mm, "TAX INVOICE")
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 20 * mm, height - 24 * mm, f"#{invoice_number}")
    c.drawRightString(width - 20 * mm, height - 29 * mm, now.strftime("%d %b %Y"))

    # ─── Bill To section ───
    y = height - 50 * mm
    c.setFillColor(dark_gray)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "BILL TO")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#555555"))
    c.drawString(20 * mm, y, tenant_name)
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Tenant ID: {tenant_id_short}")
    y -= 5 * mm
    c.drawString(20 * mm, y, "India")

    # ─── From section (right) ───
    y_from = height - 50 * mm
    c.setFillColor(dark_gray)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 20 * mm, y_from, "FROM")
    y_from -= 6 * mm
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#555555"))
    c.drawRightString(width - 20 * mm, y_from, "PRACHAR AI Technologies")
    y_from -= 5 * mm
    c.drawRightString(width - 20 * mm, y_from, "GSTIN: 29ABCDE1234F1Z5")
    y_from -= 5 * mm
    c.drawRightString(width - 20 * mm, y_from, "Bengaluru, Karnataka, India")

    # ─── Invoice items table ───
    y = height - 75 * mm
    c.setFillColor(light_gray)
    c.rect(20 * mm, y - 5 * mm, width - 40 * mm, 8 * mm, fill=1, stroke=0)
    c.setFillColor(dark_gray)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(22 * mm, y - 2 * mm, "DESCRIPTION")
    c.drawString(110 * mm, y - 2 * mm, "QTY")
    c.drawString(130 * mm, y - 2 * mm, "RATE")
    c.drawRightString(width - 22 * mm, y - 2 * mm, "AMOUNT")

    y -= 15 * mm
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#333333"))
    plan_label = f"PRACHAR {plan_key.upper()} — Monthly Subscription"
    c.drawString(22 * mm, y, plan_label)
    c.drawString(110 * mm, y, "1")
    c.drawString(130 * mm, y, f"Rs. {base_amount:,}")
    c.drawRightString(width - 22 * mm, y, f"Rs. {base_amount:,}")

    y -= 10 * mm
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#666666"))
    c.drawString(110 * mm, y, "Subtotal")
    c.drawRightString(width - 22 * mm, y, f"Rs. {base_amount:,}")

    y -= 6 * mm
    c.drawString(110 * mm, y, "GST (18%)")
    c.drawRightString(width - 22 * mm, y, f"Rs. {gst_amount:,}")

    y -= 10 * mm
    c.setFillColor(accent)
    c.rect(108 * mm, y - 3 * mm, width - 128 * mm, 8 * mm, fill=1, stroke=0)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(110 * mm, y, "TOTAL")
    c.drawRightString(width - 22 * mm, y, f"Rs. {total:,}")

    # ─── Payment status ───
    y -= 18 * mm
    c.setFillColor(dark_gray)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Payment Status:")
    status_color = HexColor("#00b894") if status_text == "active" else HexColor("#fdcb6e")
    c.setFillColor(status_color)
    c.drawString(55 * mm, y, status_text.upper())

    # ─── Footer ───
    y = 30 * mm
    c.setFillColor(light_gray)
    c.rect(0, 0, width, 25 * mm, fill=1, stroke=0)
    c.setFillColor(HexColor("#888888"))
    c.setFont("Helvetica", 8)
    c.drawString(20 * mm, y, "This is a computer-generated invoice and does not require a signature.")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Invoice #{invoice_number} | Generated on {now.strftime('%d %b %Y at %H:%M UTC')}")
    y -= 5 * mm
    c.drawString(20 * mm, y, "PRACHAR AI Technologies | GSTIN: 29ABCDE1234F1Z5 | Bengaluru, India")

    c.showPage()
    c.save()

    buf.seek(0)
    return buf.getvalue()


async def _email_invoice_after_payment(
    session: SessionDep,
    tenant_id: uuid.UUID,
    plan_key: str,
) -> None:
    """Generate a PDF invoice and email it to the tenant owner.

    Called after successful payment (Stripe or Razorpay webhook).
    Silently logs errors — never fails the webhook.
    """
    import datetime
    try:
        from ..email_service import send_invoice_email
        from ..models import User

        plan = get_plan(plan_key) or get_plan("starter")
        base_amount = plan.price_inr
        gst_amount = int(base_amount * 0.18)
        total = base_amount + gst_amount
        now = datetime.datetime.now(datetime.UTC)
        tenant_id_short = str(tenant_id)[:8].upper()
        invoice_number = f"INV-{now.strftime('%Y%m')}-{tenant_id_short}"

        # Get tenant name
        tenant_res = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_res.scalar_one_or_none()
        tenant_name = tenant.name if tenant else "Valued Customer"

        # Get owner email
        user_res = await session.execute(
            select(User).where(User.tenant_id == tenant_id).limit(1)
        )
        user = user_res.scalar_one_or_none()
        if not user or not user.email:
            log.warning("Cannot email invoice: no user found for tenant %s", tenant_id)
            return

        # Generate PDF
        pdf_bytes = _generate_invoice_pdf(
            invoice_number=invoice_number,
            tenant_name=tenant_name,
            tenant_id_short=tenant_id_short,
            plan_key=plan_key,
            base_amount=base_amount,
            gst_amount=gst_amount,
            total=total,
            status_text="active",
            now=now,
        )

        # Send email
        plan_name = plan.name if hasattr(plan, "name") else plan_key.capitalize()
        await send_invoice_email(
            to_email=user.email,
            invoice_number=invoice_number,
            plan_name=plan_name,
            total_inr=total,
            pdf_bytes=pdf_bytes,
            user_name=tenant_name,
        )
        log.info("Invoice %s emailed to %s after payment", invoice_number, user.email)

    except Exception as e:
        log.error("Failed to email invoice after payment: %s: %s", type(e).__name__, str(e)[:200])


@router.get("/invoices/{invoice_number}/pdf")
async def download_invoice_pdf(
    invoice_number: str,
    user: CurrentUser,
    session: SessionDep,
):
    """Generate and download a PDF invoice.

    Uses reportlab to generate a professional GST-compliant invoice PDF
    on-the-fly. The invoice data is computed from the tenant's billing
    record and plan pricing.
    """
    import datetime

    billing = await _get_billing(session, user.tenant_id)
    if not billing or not billing.sub_id:
        raise HTTPException(status_code=404, detail="No billing record found")

    plan_key = await get_tenant_plan(session, user)
    plan = get_plan(plan_key) or get_plan("starter")

    # Fetch tenant name
    tenant_res = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_res.scalar_one_or_none()
    tenant_name = tenant.name if tenant else "Valued Customer"

    # GST calculation (18% on plan price for India)
    base_amount = plan.price_inr
    gst_amount = int(base_amount * 0.18)
    total = base_amount + gst_amount
    now = datetime.datetime.now(datetime.UTC)

    # Verify the invoice number matches (security check)
    expected_inv = f"INV-{now.strftime('%Y%m')}-{str(user.tenant_id)[:8].upper()}"
    if invoice_number != expected_inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    status_text = billing.status.value if hasattr(billing.status, "value") else str(billing.status)
    pdf_bytes = _generate_invoice_pdf(
        invoice_number=invoice_number,
        tenant_name=tenant_name,
        tenant_id_short=str(user.tenant_id)[:8].upper(),
        plan_key=plan_key,
        base_amount=base_amount,
        gst_amount=gst_amount,
        total=total,
        status_text=status_text,
        now=now,
    )

    from fastapi.responses import StreamingResponse
    import io
    filename = f"{invoice_number}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
