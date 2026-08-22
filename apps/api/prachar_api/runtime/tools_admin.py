"""OAuth, billing, and admin tools — let the Orb initiate account-level flows.

These tools handle the things that require browser redirects or admin actions:
  • channel.connect — returns an OAuth URL for the user to click
  • billing.checkout — returns a Stripe/Razorpay checkout URL
  • billing.plans — lists available plans
  • admin.create_token — creates an API token
  • admin.list_tokens — lists API tokens
  • admin.revoke_token — revokes an API token

Architecture Freeze: Plugs into existing Tool Registry + REST API patterns.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from typing import Any

from .context import AIContext
from .registry import SideEffects, ToolCategory, ToolManifest, register_tool

log = logging.getLogger("prachar.runtime.tools_admin")


# ─── channel.connect — Get OAuth URL for connecting a channel ────────────────


@register_tool(ToolManifest(
    name="channel.connect",
    display_name="Connect Channel",
    description=(
        "Get the OAuth authorization URL for connecting a social media channel "
        "(YouTube, Instagram, Facebook, TikTok, LinkedIn, etc.). Returns a URL "
        "the user must click to authorize PRACHAR to access their account. "
        "Use when the user says 'connect my YouTube' or 'I want to link my Instagram'."
    ),
    category=ToolCategory.EXECUTION,
    input_schema={"channel": "string (e.g. youtube, instagram, facebook, tiktok, linkedin)"},
    output_schema={"channel": "string", "auth_url": "string", "instructions": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=100,
    estimated_latency_ms=500,
    quality_score=0.95,
    requires_brand=True,
    side_effects=SideEffects.NONE,
))
async def channel_connect(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Get the OAuth URL for a channel."""
    try:
        channel = (input.get("channel") or "").strip().lower()
        if not channel:
            return {"error": "channel is required", "auth_url": ""}

        from prachar_shared.adapters.registry import get_organic

        try:
            adapter = get_organic(channel)
        except KeyError:
            return {
                "error": f"no adapter for channel '{channel}'",
                "channel": channel,
                "auth_url": "",
            }

        # Generate state token (brand_id for callback)
        state = str(ctx.brand_id)
        auth_url = adapter.auth_url(state)

        return {
            "channel": channel,
            "auth_url": auth_url,
            "instructions": (
                f"Click this link to connect your {channel.title()} account. "
                "After you authorize, you'll be redirected back to PRACHAR."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("channel.connect failed: %s", exc)
        return {"error": f"connect failed: {exc}", "channel": channel if "channel" in dir() else "", "auth_url": ""}


# ─── billing.plans — List available plans ────────────────────────────────────


@register_tool(ToolManifest(
    name="billing.plans",
    display_name="Billing Plans",
    description=(
        "List all available billing plans (Starter, Growth, Agency) with "
        "pricing, features, and limits. Use when the user asks 'what plans "
        "are available' or 'how much does the Growth plan cost'."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={},
    output_schema={"plans": "array", "current_plan": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=200,
    estimated_latency_ms=500,
    quality_score=0.95,
    requires_brand=False,
    side_effects=SideEffects.READS,
))
async def billing_plans(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """List available billing plans."""
    try:
        from prachar_shared.config import get_plan_registry

        registry = get_plan_registry()
        plans = []
        for name, plan in registry.plans.items():
            plans.append({
                "name": name,
                "display_name": plan.display_name,
                "price_inr": plan.price_inr,
                "price_usd": plan.price_usd,
                "ai_token_budget": plan.ai_token_budget,
                "brand_limit": plan.brand_limit,
                "features": plan.features,
            })

        return {
            "plans": plans,
            "current_plan": ctx.billing.plan,
        }
    except Exception as exc:  # noqa: BLE001
        # Fallback: return basic plan info from context
        return {
            "plans": [
                {"name": "starter", "display_name": "Starter", "price_inr": 999, "price_usd": 12},
                {"name": "growth", "display_name": "Growth", "price_inr": 2999, "price_usd": 35},
                {"name": "agency", "display_name": "Agency", "price_inr": 9999, "price_usd": 120},
            ],
            "current_plan": ctx.billing.plan,
            "error": f"could not load full plan details: {exc}",
        }


# ─── billing.checkout — Get checkout URL for plan upgrade ────────────────────


@register_tool(ToolManifest(
    name="billing.checkout",
    display_name="Plan Checkout",
    description=(
        "Get a checkout URL for upgrading to a new plan. Returns a Stripe or "
        "Razorpay checkout URL the user must click to complete payment. "
        "Use when the user says 'upgrade to Growth' or 'I want to pay for "
        "the Agency plan'."
    ),
    category=ToolCategory.EXECUTION,
    input_schema={
        "plan": "string (starter, growth, or agency)",
        "provider": "string (optional, default stripe — or razorpay for India)",
    },
    output_schema={"checkout_url": "string", "plan": "string", "amount": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=3000,
    estimated_tokens=100,
    estimated_latency_ms=3000,
    quality_score=0.85,
    requires_brand=False,
    requires_user_approval=True,
    side_effects=SideEffects.EXTERNAL,
))
async def billing_checkout(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Get a checkout URL for plan upgrade."""
    try:
        plan = (input.get("plan") or "").strip().lower()
        if not plan or plan not in ("starter", "growth", "agency"):
            return {"error": "plan must be starter, growth, or agency", "checkout_url": ""}

        provider = (input.get("provider") or "stripe").strip().lower()

        # Build checkout URL via the billing router's internal logic
        from prachar_shared.config import get_plan_registry

        registry = get_plan_registry()
        plan_spec = registry.plans.get(plan)
        if not plan_spec:
            return {"error": f"plan '{plan}' not found", "checkout_url": ""}

        # For Stripe, create a checkout session
        if provider == "stripe":
            try:
                import stripe
                from prachar_shared.config import get_settings

                settings = get_settings()
                stripe.api_key = settings.stripe_api_key

                session = stripe.checkout.Session.create(
                    mode="subscription",
                    line_items=[{"price": plan_spec.stripe_price_id, "quantity": 1}],
                    success_url=f"/app/settings?upgraded={plan}",
                    cancel_url="/app/pricing",
                    metadata={"tenant_id": str(ctx.tenant_id), "plan": plan},
                )
                return {
                    "checkout_url": session.url,
                    "plan": plan,
                    "amount": plan_spec.price_usd,
                    "provider": "stripe",
                    "session_id": session.id,
                }
            except Exception as exc:  # noqa: BLE001
                log.warning("stripe checkout failed: %s", exc)
                return {
                    "error": f"stripe checkout failed: {exc}. Ask user to visit /app/pricing to upgrade.",
                    "checkout_url": "/app/pricing",
                    "plan": plan,
                    "amount": plan_spec.price_usd,
                }

        # For Razorpay
        elif provider == "razorpay":
            try:
                import razorpay
                from prachar_shared.config import get_settings

                settings = get_settings()
                client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))

                order = client.order.create({
                    "amount": plan_spec.price_inr * 100,  # paise
                    "currency": "INR",
                    "notes": {"tenant_id": str(ctx.tenant_id), "plan": plan},
                })
                return {
                    "checkout_url": f"/app/pricing?order_id={order['id']}&plan={plan}",
                    "plan": plan,
                    "amount": plan_spec.price_inr,
                    "provider": "razorpay",
                    "order_id": order["id"],
                }
            except Exception as exc:  # noqa: BLE001
                log.warning("razorpay checkout failed: %s", exc)
                return {
                    "error": f"razorpay checkout failed: {exc}. Ask user to visit /app/pricing to upgrade.",
                    "checkout_url": "/app/pricing",
                    "plan": plan,
                    "amount": plan_spec.price_inr,
                }

        return {"error": f"unknown provider '{provider}'", "checkout_url": ""}
    except Exception as exc:  # noqa: BLE001
        log.exception("billing.checkout failed: %s", exc)
        return {"error": f"checkout failed: {exc}", "checkout_url": ""}


# ─── admin.create_token — Create an API token ────────────────────────────────


@register_tool(ToolManifest(
    name="admin.create_token",
    display_name="Create API Token",
    description=(
        "Create a new API access token for programmatic access. "
        "Requires owner/admin role. Use when the user says 'create an API "
        "token' or 'generate an API key'."
    ),
    category=ToolCategory.EXECUTION,
    input_schema={"name": "string", "scopes": "array (optional, default ['read'])"},
    output_schema={"token": "string", "name": "string", "scopes": "array"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=0,
    estimated_latency_ms=500,
    quality_score=0.95,
    requires_brand=False,
    requires_user_approval=True,
    side_effects=SideEffects.WRITES,
    required_role="admin",
))
async def admin_create_token(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Create an API token."""
    try:
        name = (input.get("name") or "").strip()
        if not name:
            return {"error": "token name is required", "token": ""}

        scopes = input.get("scopes", ["read"])

        # Generate token
        raw_token = f"prachar_{secrets.token_urlsafe(32)}"

        # Store in the admin router's in-memory store
        from ..routers.admin import _api_tokens

        token_id = uuid.uuid4()
        _api_tokens[raw_token] = {
            "id": token_id,
            "name": name,
            "scopes": scopes,
            "tenant_id": ctx.tenant_id,
            "created_at": "2026-07-16T00:00:00Z",
        }

        # Audit
        from ..audit import log_audit
        await log_audit(
            ctx.session,
            tenant_id=ctx.tenant_id,
            actor="orb",
            action="api_token.created",
            entity_type="api_token",
            entity_id=str(token_id),
            payload={"name": name, "scopes": scopes},
        )

        return {
            "token": raw_token,
            "name": name,
            "scopes": scopes,
            "token_id": str(token_id),
            "message": f"API token '{name}' created. Save it securely — it won't be shown again.",
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("admin.create_token failed: %s", exc)
        return {"error": f"create token failed: {exc}", "token": ""}


# ─── admin.list_tokens — List API tokens ─────────────────────────────────────


@register_tool(ToolManifest(
    name="admin.list_tokens",
    display_name="List API Tokens",
    description=(
        "List all API access tokens for this workspace. Returns name, "
        "scopes, and creation date (tokens are masked). Use when the user "
        "asks 'show my API tokens' or 'what API keys do I have'."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={},
    output_schema={"tokens": "array", "count": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=300,
    estimated_tokens=100,
    estimated_latency_ms=300,
    quality_score=0.95,
    requires_brand=False,
    side_effects=SideEffects.READS,
    required_role="admin",
))
async def admin_list_tokens(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """List API tokens."""
    try:
        from ..routers.admin import _api_tokens

        tokens = []
        for token, info in _api_tokens.items():
            if info["tenant_id"] == ctx.tenant_id:
                tokens.append({
                    "id": str(info["id"]),
                    "name": info["name"],
                    "token": token[:12] + "...",  # masked
                    "scopes": info["scopes"],
                    "created_at": info["created_at"],
                })

        return {"tokens": tokens, "count": len(tokens)}
    except Exception as exc:  # noqa: BLE001
        log.exception("admin.list_tokens failed: %s", exc)
        return {"error": f"list tokens failed: {exc}", "tokens": [], "count": 0}


# ─── admin.revoke_token — Revoke an API token ────────────────────────────────


@register_tool(ToolManifest(
    name="admin.revoke_token",
    display_name="Revoke API Token",
    description=(
        "Reocate an API access token by name. The token will no longer work. "
        "Use when the user says 'revoke my API token' or 'delete that API key'."
    ),
    category=ToolCategory.EXECUTION,
    input_schema={"name": "string"},
    output_schema={"status": "string", "name": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=300,
    estimated_tokens=0,
    estimated_latency_ms=300,
    quality_score=0.95,
    requires_brand=False,
    requires_user_approval=True,
    side_effects=SideEffects.WRITES,
    required_role="admin",
))
async def admin_revoke_token(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Revoke an API token by name."""
    try:
        from ..routers.admin import _api_tokens

        name = (input.get("name") or "").strip()
        if not name:
            return {"error": "token name is required", "status": "failed"}

        # Find and remove token
        to_remove = None
        for token, info in _api_tokens.items():
            if info["tenant_id"] == ctx.tenant_id and info["name"] == name:
                to_remove = token
                break

        if to_remove:
            del _api_tokens[to_remove]
            # Audit
            from ..audit import log_audit
            await log_audit(
                ctx.session,
                tenant_id=ctx.tenant_id,
                actor="orb",
                action="api_token.revoked",
                entity_type="api_token",
                entity_id=name,
            )
            return {"status": "revoked", "name": name, "message": f"Token '{name}' has been revoked."}
        else:
            return {"error": f"token '{name}' not found", "status": "failed"}
    except Exception as exc:  # noqa: BLE001
        log.exception("admin.revoke_token failed: %s", exc)
        return {"error": f"revoke failed: {exc}", "status": "failed"}
