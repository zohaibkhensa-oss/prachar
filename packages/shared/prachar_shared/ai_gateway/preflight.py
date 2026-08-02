"""Pre-flight budget estimation for workflows.

Before executing a workflow (e.g., weekly loop), estimate the token cost
and check if the tenant has sufficient budget. If not, inform the user
before work begins.

Usage:
    from prachar_shared.ai_gateway.preflight import estimate_workflow_cost, preflight_check

    estimate = estimate_workflow_cost("weekly_loop", channels=["google", "youtube"])
    check = preflight_check(tenant_id, plan="growth", workflow="weekly_loop")
    if not check.can_proceed:
        raise InsufficientBudget(check.message)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowEstimate:
    """Estimated token cost for a workflow."""

    workflow: str
    estimated_tokens: int
    estimated_cost_usd: float
    steps: dict[str, int] = field(default_factory=dict)  # step_name -> tokens
    notes: str = ""


@dataclass
class PreflightResult:
    """Result of a pre-flight budget check."""

    can_proceed: bool
    workflow: str
    estimated_tokens: int
    available_tokens: int
    shortfall: int
    message: str
    estimate: WorkflowEstimate | None = None


class InsufficientBudget(Exception):
    """Raised when a workflow cannot proceed due to insufficient budget."""

    def __init__(self, message: str, result: PreflightResult | None = None) -> None:
        super().__init__(message)
        self.result = result


# ─── Workflow cost models ─────────────────────────────────────────────────────
# Token estimates per step, calibrated from actual measurements.
# These are conservative (upper-bound) estimates.

_STEP_TOKENS: dict[str, int] = {
    # Loop steps
    "measure": 500,  # metric aggregation, minimal AI
    "diagnose": 2000,  # AI gap analysis
    "regenerate": 1000,  # per channel — multiplied by channel count
    "policy_check": 250,  # per channel — claims gate check
    "publish": 200,  # minimal AI
    "budget_realloc": 500,  # AI allocation decisions
    "report": 3000,  # AI report generation
    # Individual tasks
    "chat": 500,
    "content_generation": 1000,  # per channel per locale
    "meta_generation": 400,
    "creative_copy": 800,
    "audit_findings": 2000,
    "entity_extraction": 300,
    "citation_probe": 200,
    "video_script": 1500,
    "image_generation": 0,  # GPU cost, not tokens
    "video_generation": 0,  # GPU cost, not tokens
}

# Default channels for weekly loop
_DEFAULT_CHANNELS = [
    "google", "gsc", "gmb", "youtube", "instagram",
    "facebook", "tiktok", "linkedin", "x", "pinterest",
]


def estimate_workflow_cost(
    workflow: str,
    *,
    channels: list[str] | None = None,
    locales: int = 1,
) -> WorkflowEstimate:
    """Estimate the token cost of a workflow.

    Args:
        workflow: Workflow name (e.g., "weekly_loop", "single_content_gen").
        channels: List of channels to process. Defaults to all 10.
        locales: Number of locales to generate content for.

    Returns:
        WorkflowEstimate with token and cost breakdown.
    """
    ch_count = len(channels) if channels else len(_DEFAULT_CHANNELS)

    if workflow == "weekly_loop":
        steps = {
            "measure": _STEP_TOKENS["measure"],
            "diagnose": _STEP_TOKENS["diagnose"],
            "regenerate": _STEP_TOKENS["regenerate"] * ch_count * locales,
            "policy_check": _STEP_TOKENS["policy_check"] * ch_count * locales,
            "publish": _STEP_TOKENS["publish"],
            "budget_realloc": _STEP_TOKENS["budget_realloc"],
            "report": _STEP_TOKENS["report"],
        }
        total = sum(steps.values())
        # Cost estimate: Groq llama-3.3-70b ~$0.70/1M tokens blended
        cost = total / 1_000_000 * 0.70
        return WorkflowEstimate(
            workflow=workflow,
            estimated_tokens=total,
            estimated_cost_usd=round(cost, 4),
            steps=steps,
            notes=f"Based on {ch_count} channels × {locales} locale(s)",
        )

    if workflow == "single_content_gen":
        total = _STEP_TOKENS["content_generation"] * ch_count * locales
        cost = total / 1_000_000 * 0.70
        return WorkflowEstimate(
            workflow=workflow,
            estimated_tokens=total,
            estimated_cost_usd=round(cost, 4),
            steps={"content_generation": total},
            notes=f"Based on {ch_count} channels × {locales} locale(s)",
        )

    if workflow == "audit":
        total = _STEP_TOKENS["entity_extraction"] + _STEP_TOKENS["audit_findings"] + _STEP_TOKENS["citation_probe"]
        cost = total / 1_000_000 * 0.70
        return WorkflowEstimate(
            workflow=workflow,
            estimated_tokens=total,
            estimated_cost_usd=round(cost, 4),
            steps={
                "entity_extraction": _STEP_TOKENS["entity_extraction"],
                "audit_findings": _STEP_TOKENS["audit_findings"],
                "citation_probe": _STEP_TOKENS["citation_probe"],
            },
        )

    if workflow == "chat":
        total = _STEP_TOKENS["chat"]
        cost = total / 1_000_000 * 0.10  # Small model cheaper
        return WorkflowEstimate(
            workflow=workflow,
            estimated_tokens=total,
            estimated_cost_usd=round(cost, 6),
            steps={"chat": total},
        )

    # Unknown workflow — return conservative estimate
    return WorkflowEstimate(
        workflow=workflow,
        estimated_tokens=50000,
        estimated_cost_usd=0.035,
        notes="Unknown workflow — using conservative default",
    )


def preflight_check(
    tenant_id: Any,
    plan: str,
    workflow: str,
    *,
    channels: list[str] | None = None,
    locales: int = 1,
) -> PreflightResult:
    """Check if a tenant has sufficient budget for a workflow.

    Args:
        tenant_id: The tenant UUID.
        plan: The tenant's plan ("starter", "growth", "agency").
        workflow: The workflow to check.
        channels: Channels to process.
        locales: Number of locales.

    Returns:
        PreflightResult indicating whether the workflow can proceed.
    """
    from .budget import BudgetGuard

    estimate = estimate_workflow_cost(workflow, channels=channels, locales=locales)
    guard = BudgetGuard()
    available = guard.remaining(tenant_id, plan)

    if available >= estimate.estimated_tokens:
        return PreflightResult(
            can_proceed=True,
            workflow=workflow,
            estimated_tokens=estimate.estimated_tokens,
            available_tokens=available,
            shortfall=0,
            message=(
                f"Workflow '{workflow}' estimated to use {estimate.estimated_tokens:,} tokens "
                f"(~${estimate.estimated_cost_usd:.4f}). You have {available:,} tokens available."
            ),
            estimate=estimate,
        )

    shortfall = estimate.estimated_tokens - available
    return PreflightResult(
        can_proceed=False,
        workflow=workflow,
        estimated_tokens=estimate.estimated_tokens,
        available_tokens=available,
        shortfall=shortfall,
        message=(
            f"Insufficient budget for workflow '{workflow}'. "
            f"Estimated: {estimate.estimated_tokens:,} tokens. "
            f"Available: {available:,} tokens. "
            f"Shortfall: {shortfall:,} tokens. "
            f"Please upgrade your plan or wait for the monthly budget reset."
        ),
        estimate=estimate,
    )


def get_workflow_estimates() -> dict[str, Any]:
    """Get cost estimates for all known workflows (for documentation/API)."""
    workflows = {}
    for wf in ["weekly_loop", "single_content_gen", "audit", "chat"]:
        workflows[wf] = {
            "estimated_tokens": estimate_workflow_cost(wf).estimated_tokens,
            "estimated_cost_usd": estimate_workflow_cost(wf).estimated_cost_usd,
            "steps": estimate_workflow_cost(wf).steps,
        }
    return workflows
