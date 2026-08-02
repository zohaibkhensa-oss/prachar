"""Learning Engine.

After a campaign, collects CTR, reach, impressions, comments, shares,
conversions, cost, ROI. Generates a learning report. Future campaigns
improve automatically based on this learning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prachar_shared.ai_gateway import Completion, Tier

from .base import EngineOutput, IntelligenceEngine
from .domain_base import DomainModel


@dataclass
class LearningReport(DomainModel):
    """Post-campaign learning report.

    Inherits from_dict()/validate()/schema_version() from DomainModel.
    Owned by LearningEngine.
    """

    performance_summary: dict[str, Any] = field(default_factory=dict)
    what_worked: list[str] = field(default_factory=list)
    what_didnt_work: list[str] = field(default_factory=list)
    key_learnings: list[str] = field(default_factory=list)
    recommendations_for_next_campaign: list[str] = field(default_factory=list)
    benchmark_comparison: dict[str, Any] = field(default_factory=dict)
    audience_insights: dict[str, Any] = field(default_factory=dict)
    creative_insights: dict[str, Any] = field(default_factory=dict)
    channel_insights: dict[str, Any] = field(default_factory=dict)
    updated_best_practices: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "performance_summary": self.performance_summary,
            "what_worked": self.what_worked,
            "what_didnt_work": self.what_didnt_work,
            "key_learnings": self.key_learnings,
            "recommendations_for_next_campaign": self.recommendations_for_next_campaign,
            "benchmark_comparison": self.benchmark_comparison,
            "audience_insights": self.audience_insights,
            "creative_insights": self.creative_insights,
            "channel_insights": self.channel_insights,
            "updated_best_practices": self.updated_best_practices,
        }


class LearningEngine(IntelligenceEngine):
    """Analyzes campaign performance and generates learnings for future campaigns."""

    ENGINE_NAME = "learning_engine"
    ENGINE_VERSION = "1.0.0"
    PROMPT_VERSION = "1.0.0"
    SCHEMA_VERSION = "1.0.0"
    TIER = Tier.large
    MAX_TOKENS = 2500
    TEMPERATURE = 0.3

    def _build_prompt(self, **kwargs: Any) -> str:
        campaign_plan = kwargs.get("campaign_plan", {})
        performance_data = kwargs.get("performance_data", {})
        business_memory = kwargs.get("business_memory", {})
        historical_campaigns = kwargs.get("historical_campaigns", [])
        additional_context = kwargs.get("additional_context", "")

        return f"""ROLE: You are a senior analytics & insights director at a top agency. You 
extract actionable learnings from campaign data with the rigor of a data scientist 
and the strategic insight of a brand consultant. You don't just report numbers — 
you explain WHY and WHAT TO DO NEXT.

TASK: Analyze campaign performance and generate a learning report.

INPUTS:
- Campaign Plan: {campaign_plan}
- Performance Data: {performance_data}
- Business Memory (historical context): {business_memory}
- Historical Campaigns: {historical_campaigns}
{f"- Additional Context: {additional_context}" if additional_context else ""}

LEARNING REPORT REQUIREMENTS:
1. Performance Summary: Key metrics vs. targets:
   - CTR, Reach, Impressions, Comments, Shares, Conversions, Cost, ROI
   - Did we hit KPIs? By how much?
2. What Worked: 3-5 specific things that drove results.
3. What Didn't Work: 3-5 specific things that underperformed.
4. Key Learnings: 5-7 insights to apply to future campaigns.
5. Recommendations for Next Campaign: Specific, actionable changes.
6. Benchmark Comparison: How this campaign compares to industry benchmarks
   and to the brand's historical performance.
7. Audience Insights: What we learned about the audience.
8. Creative Insights: Which creative elements performed best.
9. Channel Insights: Which channels delivered best ROI.
10. Updated Best Practices: Recommendations to add to the brand's playbook.

QUALITY RULES:
- Every insight must be tied to specific data
- "What worked" and "What didn't work" must be specific, not generic
- Learnings must be actionable for future campaigns
- Compare to historical performance if available
- Confidence 0.4-0.8
- 3-5 strategic recommendations

OUTPUT: JSON matching the schema. Include "reasoning", "confidence", "recommendations".
"""

    def _build_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "performance_summary": {
                    "type": "object",
                    "properties": {
                        "metrics_vs_target": {"type": "array", "items": {"type": "object"}},
                        "overall_grade": {"type": "string"},
                        "headline_finding": {"type": "string"},
                    },
                },
                "what_worked": {"type": "array", "items": {"type": "string"}},
                "what_didnt_work": {"type": "array", "items": {"type": "string"}},
                "key_learnings": {"type": "array", "items": {"type": "string"}},
                "recommendations_for_next_campaign": {"type": "array", "items": {"type": "string"}},
                "benchmark_comparison": {
                    "type": "object",
                    "properties": {
                        "vs_industry": {"type": "string"},
                        "vs_historical": {"type": "string"},
                        "analysis": {"type": "string"},
                    },
                },
                "audience_insights": {
                    "type": "object",
                    "properties": {
                        "top_segments": {"type": "array", "items": {"type": "string"}},
                        "surprising_findings": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "creative_insights": {
                    "type": "object",
                    "properties": {
                        "best_performing": {"type": "array", "items": {"type": "string"}},
                        "worst_performing": {"type": "array", "items": {"type": "string"}},
                        "patterns": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "channel_insights": {
                    "type": "object",
                    "properties": {
                        "best_roi_channels": {"type": "array", "items": {"type": "string"}},
                        "underperforming_channels": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "updated_best_practices": {"type": "array", "items": {"type": "string"}},
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
            "required": ["performance_summary", "key_learnings", "reasoning", "confidence"],
        }

    def to_report(self, output: EngineOutput) -> LearningReport:
        """Convert an EngineOutput to a typed LearningReport.

        Delegates to LearningReport.from_dict() — the model owns parsing.
        """
        return LearningReport.from_dict(output.result)  # type: ignore[return-value]
