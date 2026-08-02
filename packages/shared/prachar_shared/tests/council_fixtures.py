"""Shared test fixtures for Agency Council tests."""
from __future__ import annotations

from typing import Any

from prachar_shared.ai_gateway import Completion


class StubGateway:
    """Deterministic stub gateway for council tests.

    Returns predictable opinions for each director based on the task name.
    """

    def __init__(self, *, approval_mode: str = "all_approve") -> None:
        self.calls: list[dict[str, Any]] = []
        self.approval_mode = approval_mode

    def complete(self, **kw: Any) -> Completion:
        self.calls.append(kw)
        task = kw.get("task", "generic")

        # Self-critique returns critiques
        if task == "council_self_critique":
            return Completion(
                text="[stub]", json_value={"critiques": [
                    "The campaign may be too generic",
                    "Competitors could undercut on price",
                ]},
                tokens_used=50, model="stub", provider="stub",
                latency_ms=5.0, cost_usd=0.001, request_id="critique-req",
                confidence=0.7,
            )

        # Director opinions
        approval = self._get_approval(task)
        confidence = self._get_confidence(task)
        priority = self._get_priority(task)

        result: dict[str, Any] = {
            "opinion": f"{task} opinion: campaign looks good",
            "reasoning": f"{task} reasoning: based on the brief, this campaign is appropriate",
            "confidence": confidence,
            "risks": [f"{task} risk: budget may be tight"] if priority in ("high", "critical") else [],
            "alternatives": [f"Consider alternative approach for {task}"],
            "recommendations": [f"{task} recommends proceeding with adjustments"],
            "evidence": ["Brief section: business_name", "Brief section: objective"],
            "priority": priority,
            "approval": approval,
        }

        return Completion(
            text="[stub]", json_value=result,
            tokens_used=100, model="stub", provider="stub",
            latency_ms=10.0, cost_usd=0.002, request_id=f"req-{task}",
            confidence=confidence,
        )

    def _get_approval(self, task: str) -> bool:
        if self.approval_mode == "all_approve":
            return True
        elif self.approval_mode == "all_reject":
            return False
        elif self.approval_mode == "split":
            # Compliance and Finance reject, others approve
            return task not in ("chief_compliance_officer", "chief_financial_officer")
        elif self.approval_mode == "compliance_rejects":
            return task != "chief_compliance_officer"
        return True

    def _get_confidence(self, task: str) -> float:
        if self.approval_mode == "all_approve":
            return 0.8
        elif self.approval_mode == "all_reject":
            return 0.3
        elif self.approval_mode == "split":
            if task in ("chief_compliance_officer", "chief_financial_officer"):
                return 0.4
            return 0.75
        elif self.approval_mode == "compliance_rejects":
            if task == "chief_compliance_officer":
                return 0.2
            return 0.8
        return 0.7

    def _get_priority(self, task: str) -> str:
        if self.approval_mode == "compliance_rejects" and task == "chief_compliance_officer":
            return "critical"
        if self.approval_mode == "split" and task == "chief_compliance_officer":
            return "high"
        return "medium"


class FailingGateway:
    """Gateway that always fails — for testing error handling."""

    def complete(self, **kw: Any) -> Completion:
        raise RuntimeError("Gateway unavailable")
