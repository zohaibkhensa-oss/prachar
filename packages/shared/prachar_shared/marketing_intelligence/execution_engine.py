"""Execution Planner.

Breaks a campaign into executable tasks: strategy → creative → images →
videos → copy → landing page → approval → publishing → monitoring →
optimization.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prachar_shared.ai_gateway import Completion, Tier

from .base import EngineOutput, IntelligenceEngine
from .domain_base import DomainModel


@dataclass
class ExecutionPlan(DomainModel):
    """Campaign execution plan with task breakdown.

    Inherits from_dict()/validate()/schema_version() from DomainModel.
    Owned by ExecutionPlanner.
    """

    phases: list[dict[str, Any]] = field(default_factory=list)
    tasks: list[dict[str, Any]] = field(default_factory=list)
    timeline: dict[str, Any] = field(default_factory=dict)
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    approval_checklist: list[str] = field(default_factory=list)
    ai_asset_requirements: list[dict[str, Any]] = field(default_factory=list)
    risk_mitigation: list[dict[str, Any]] = field(default_factory=list)
    weekly_timeline: list[dict[str, Any]] = field(default_factory=list)
    dependency_map: list[dict[str, Any]] = field(default_factory=list)
    risk_mitigation_plan: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phases": self.phases,
            "tasks": self.tasks,
            "timeline": self.timeline,
            "dependencies": self.dependencies,
            "approval_checklist": self.approval_checklist,
            "ai_asset_requirements": self.ai_asset_requirements,
            "risk_mitigation": self.risk_mitigation,
            "weekly_timeline": self.weekly_timeline,
            "dependency_map": self.dependency_map,
            "risk_mitigation_plan": self.risk_mitigation_plan,
        }


class ExecutionPlanner(IntelligenceEngine):
    """Breaks campaign strategy into an executable task plan."""

    ENGINE_NAME = "execution_planner"
    ENGINE_VERSION = "1.1.0"
    PROMPT_VERSION = "2.0.0"
    SCHEMA_VERSION = "1.1.0"
    TIER = Tier.large
    MAX_TOKENS = 3500
    TEMPERATURE = 0.2  # Low temperature for structured planning

    def _build_prompt(self, **kwargs: Any) -> str:
        campaign_strategy = kwargs.get("campaign_strategy", {})
        creative_direction = kwargs.get("creative_direction", {})
        media_plan = kwargs.get("media_plan", {})
        budget_estimate = kwargs.get("budget_estimate", {})
        objective = kwargs.get("objective", {})
        additional_context = kwargs.get("additional_context", "")

        return f"""ROLE: You are a senior Project Manager at a top advertising agency. You break
campaigns into executable tasks with the precision of a military operations planner
and the practicality of a seasoned producer. You plan week-by-week with clear
milestones, map dependencies so nothing blocks silently, and pre-empt risks
before they become fires.

TASK: Create a detailed execution plan for this campaign with a week-by-week
timeline, dependency mapping, and a risk mitigation plan.

INPUTS:
- Campaign Strategy: {campaign_strategy}
- Creative Direction: {creative_direction}
- Media Plan: {media_plan}
- Budget Estimate: {budget_estimate}
- Marketing Objective: {objective}
{f"- Additional Context: {additional_context}" if additional_context else ""}

REASONING PROCESS (follow this chain-of-thought before producing your answer):
Step 1 — PHASES: Break the campaign into phases (strategy, creative, landing page,
  approval, publishing, monitoring, reporting). What is the logical sequence?
Step 2 — WEEKLY: Break each phase into week-by-week tasks with specific milestones.
  What must be done in week 1, week 2, etc.? What is the milestone at the end of each week?
Step 3 — DEPENDENCIES: Map what must happen before what. Which tasks are on the
  critical path? Which can run in parallel? Where are the bottlenecks?
Step 4 — RISKS: What could go wrong? For each risk: what is the probability, what is
  the impact, and what is the mitigation? What is the contingency plan?
Step 5 — APPROVALS: What needs sign-off before publishing? Who approves what?
  What is the approval SLA?
Write your reasoning in the "reasoning" field showing this step-by-step analysis.

EXECUTION PLAN REQUIREMENTS:
1. Phases: Break the campaign into phases:
   - Phase 1: Strategy & Planning (finalized)
   - Phase 2: Creative Production (images, videos, copy)
   - Phase 3: Landing Page & Assets
   - Phase 4: Approval & Compliance
   - Phase 5: Publishing & Distribution
   - Phase 6: Monitoring & Optimization
   - Phase 7: Reporting & Learning
2. Tasks: For each phase, list specific tasks with:
   - Task name, description, estimated duration
   - Assigned role (AI, human, both)
   - Dependencies (what must be done first)
   - Deliverable
3. Timeline: Gantt-style timeline with start/end dates.
4. Dependencies: Critical path analysis.
5. Approval Checklist: What needs sign-off before publishing.
6. AI Asset Requirements: List of all AI-generated assets needed:
   - Images (count, style, dimensions)
   - Videos (count, duration, style)
   - Copy (count, type, channel)
7. Risk Mitigation: What could go wrong and how to prevent it.
8. Weekly Timeline: Week-by-week breakdown with milestones. For each week:
   - week: Week number (1, 2, 3, etc.)
   - phase: Which phase this week belongs to
   - key_tasks: 2-5 specific tasks for this week
   - milestone: The deliverable or checkpoint at end of week
   - deliverables: What is produced this week
   - assigned_to: Who is responsible (AI, human, both)
   - status: "planned" (default for all weeks)
   - dependencies_completed: What must be done before this week starts
   - risk_flags: Any risks to watch this week (e.g., "Creative approval may delay week 3")
9. Dependency Map: Detailed dependency mapping. For each dependency:
   - task: The task that depends on something
   - depends_on: The task it depends on
   - dependency_type: "hard" (cannot start without it) or "soft" (can start but
     quality/efficiency improves with it)
   - lead_time: How long after the dependency is completed can this task start?
     (e.g., "0 days (immediate)", "2 days (setup required)")
   - bottleneck: Is this dependency on the critical path? (true/false)
   - parallel_tasks: What can run in parallel while waiting for this dependency?
10. Risk Mitigation Plan: Comprehensive risk plan. For each risk:
    - risk: What could go wrong (specific, not generic "delays")
    - probability: low / medium / high
    - impact: low / medium / high / critical
    - trigger_signal: How will we know this risk is materialising?
      (e.g., "AI image quality below threshold in first batch", "Approval not received by day 3")
    - mitigation: What we do to prevent it
    - contingency: What we do if it happens (Plan B)
    - owner: Who is responsible for monitoring this risk (AI, human, both)
    - escalation: When/how to escalate (e.g., "If approval > 48h overdue, escalate to agency lead")

FEW-SHOT EXAMPLE (D2C Coffee, 12-week campaign — use as quality benchmark, do NOT copy):
- Weekly Timeline:
  - week 1: phase="Creative Production", key_tasks=["Generate 10 product images (AI)",
    "Write 5 Instagram captions (AI)", "Draft 2 Reel scripts (AI)"],
    milestone="All creative assets drafted and ready for review",
    deliverables="10 images, 5 captions, 2 Reel scripts", assigned_to="AI",
    dependencies_completed="Strategy approved, creative direction approved",
    risk_flags="AI image quality may need 2 iterations"
  - week 2: phase="Creative Production + Landing Page",
    key_tasks=["Revise images based on feedback", "Build landing page", "Set up tracking pixels"],
    milestone="Landing page live, all creative assets approved",
    deliverables="Approved creative pack, live landing page, tracking verified",
    assigned_to="both", dependencies_completed="Week 1 creative drafts",
    risk_flags="Landing page development may take 3 days if custom design needed"
  - week 3: phase="Approval & Publishing", key_tasks=["Claims gate review",
    "Brand guidelines check", "Publish first 3 Reels", "Launch Instagram ads"],
    milestone="Campaign LIVE", deliverables="Campaign launched on Instagram + Google",
    assigned_to="both", dependencies_completed="Week 2 landing page + creative approval",
    risk_flags="Claims gate may flag 'direct trade' — prepare substantiation"
- Dependency Map:
  - task: "Publish Reels", depends_on: "Creative approval", dependency_type: "hard",
    lead_time: "0 days", bottleneck: true,
    parallel_tasks: "Landing page development, pixel setup, audience targeting config"
  - task: "Launch retargeting ads", depends_on: "First 100 visitors to landing page",
    dependency_type: "hard", lead_time: "2-3 days (wait for pixel data)",
    bottleneck: false, parallel_tasks: "Continue organic posting, build email list"
- Risk Mitigation Plan:
  - risk: "AI-generated images don't match brand aesthetic (too synthetic)",
    probability: "medium", impact: "high",
    trigger_signal: "First batch of images < 70% approval rate in review",
    mitigation: "Provide 3 reference images per prompt, use brand colour palette in prompts,
      run 2 iterations before final selection",
    contingency: "Commission human photographer for 5 hero shots (₹15,000, 3-day turnaround)",
    owner: "both", escalation: "If 2nd iteration < 80% approval, switch to human photographer"
  - risk: "Claims gate flags 'direct trade' as unverifiable",
    probability: "medium", impact: "critical",
    trigger_signal: "Claims gate returns False on first submission",
    mitigation: "Prepare direct trade certificates and farmer contracts as substantiation
      before submission",
    contingency: "Rephrase to 'sourced directly from named farmers' with farmer names
      visible in creative",
    owner: "human", escalation: "If claims gate fails twice, legal review before re-submission"

QUALITY RULES:
- Tasks must be specific and actionable, not vague
- Durations must be realistic
- Dependencies must form a logical critical path
- Weekly timeline must have clear milestones — not just "do stuff"
- Dependency map must identify bottlenecks and parallelisable tasks
- Risk mitigation must include trigger signals — not just "monitor and adapt"
- Contingency plans must be specific and actionable, not "we'll figure it out"
- AI asset requirements must be precise enough for automated generation
- Confidence 0.5-0.9 (planning is more deterministic than analysis)
- 3-5 execution recommendations

OUTPUT: JSON matching the schema. Include "reasoning", "confidence", "recommendations".
"""

    def _build_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "phases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "phase": {"type": "string"},
                            "description": {"type": "string"},
                            "duration_days": {"type": "number"},
                            "start_after": {"type": "string"},
                        },
                    },
                },
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string"},
                            "phase": {"type": "string"},
                            "description": {"type": "string"},
                            "duration_hours": {"type": "number"},
                            "assigned_to": {"type": "string"},  # AI, human, both
                            "dependencies": {"type": "array", "items": {"type": "string"}},
                            "deliverable": {"type": "string"},
                        },
                    },
                },
                "timeline": {
                    "type": "object",
                    "properties": {
                        "total_duration_days": {"type": "number"},
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "critical_path": {"type": "string"},
                    },
                },
                "dependencies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string"},
                            "depends_on": {"type": "string"},
                            "type": {"type": "string"},  # hard, soft
                        },
                    },
                },
                "approval_checklist": {"type": "array", "items": {"type": "string"}},
                "ai_asset_requirements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "asset_type": {"type": "string"},  # image, video, copy
                            "count": {"type": "number"},
                            "specifications": {"type": "string"},
                            "channel": {"type": "string"},
                            "priority": {"type": "string"},
                        },
                    },
                },
                "risk_mitigation": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "risk": {"type": "string"},
                            "probability": {"type": "string"},  # low, medium, high
                            "impact": {"type": "string"},
                            "mitigation": {"type": "string"},
                        },
                    },
                },
                "weekly_timeline": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "week": {"type": "number"},
                            "phase": {"type": "string"},
                            "key_tasks": {"type": "array", "items": {"type": "string"}},
                            "milestone": {"type": "string"},
                            "deliverables": {"type": "string"},
                            "assigned_to": {"type": "string"},
                            "status": {"type": "string"},
                            "dependencies_completed": {"type": "string"},
                            "risk_flags": {"type": "string"},
                        },
                    },
                },
                "dependency_map": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task": {"type": "string"},
                            "depends_on": {"type": "string"},
                            "dependency_type": {"type": "string"},
                            "lead_time": {"type": "string"},
                            "bottleneck": {"type": "boolean"},
                            "parallel_tasks": {"type": "string"},
                        },
                    },
                },
                "risk_mitigation_plan": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "risk": {"type": "string"},
                            "probability": {"type": "string"},
                            "impact": {"type": "string"},
                            "trigger_signal": {"type": "string"},
                            "mitigation": {"type": "string"},
                            "contingency": {"type": "string"},
                            "owner": {"type": "string"},
                            "escalation": {"type": "string"},
                        },
                    },
                },
                "reasoning": {"type": "string"},
                "confidence": {"type": "number"},
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "confidence": {"type": "number"},
                            "business_rationale": {"type": "string"},
                            "marketing_rationale": {"type": "string"},
                            "alternatives": {"type": "array", "items": {"type": "string"}},
                            "risks": {"type": "array", "items": {"type": "string"}},
                            "expected_outcome": {"type": "string"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                            "sources": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
            "required": ["phases", "tasks", "reasoning", "confidence"],
        }

    def to_plan(self, output: EngineOutput) -> ExecutionPlan:
        """Convert an EngineOutput to a typed ExecutionPlan.

        Delegates to ExecutionPlan.from_dict() — the model owns parsing.
        """
        return ExecutionPlan.from_dict(output.result)  # type: ignore[return-value]
