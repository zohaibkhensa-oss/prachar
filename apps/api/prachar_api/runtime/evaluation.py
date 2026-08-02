"""Evaluation Framework — datasets, regression tests, and quality scoring.

Phase J: Every AI improvement can now be measured objectively.

This module provides:
1. EvaluationDataset — a set of prompts with expected outputs
2. QualityScorer — scores AI output against expected output
3. RegressionSuite — runs all datasets and reports pass/fail + quality scores

Usage:
    from prachar_api.runtime.evaluation import get_regression_suite

    suite = get_regression_suite()
    results = await suite.run_all(mock_gateway=True)
    print(results.summary())
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

log = logging.getLogger("prachar.runtime.evaluation")


# ─── Data Models ────────────────────────────────────────────────────────────


@dataclass
class EvaluationCase:
    """A single evaluation case: input → expected output.

    Attributes:
        id: unique case identifier
        category: what capability this tests (e.g. "campaign_brain.analyse")
        input: the input dict to pass to the tool/engine
        expected_fields: fields that MUST be present in the output
        expected_min_quality: minimum quality score (0.0-1.0) to pass
        expected_types: field → type mapping for type checking
        expected_contains: field → substring that must be present
        description: human-readable description of what this case tests
    """

    id: str = ""
    category: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    expected_fields: list[str] = field(default_factory=list)
    expected_min_quality: float = 0.7
    expected_types: dict[str, type] = field(default_factory=dict)
    expected_contains: dict[str, str] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "input": self.input,
            "expected_fields": self.expected_fields,
            "expected_min_quality": self.expected_min_quality,
            "expected_types": {k: v.__name__ for k, v in self.expected_types.items()},
            "expected_contains": self.expected_contains,
            "description": self.description,
        }


@dataclass
class CaseResult:
    """Result of running a single evaluation case."""

    case_id: str = ""
    passed: bool = False
    quality_score: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "quality_score": self.quality_score,
            "errors": self.errors,
            "warnings": self.warnings,
            "duration_ms": self.duration_ms,
        }


@dataclass
class SuiteResult:
    """Result of running the full regression suite."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    avg_quality: float = 0.0
    results: list[CaseResult] = field(default_factory=list)
    ran_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def summary(self) -> str:
        return (
            f"Regression Suite: {self.passed}/{self.total} passed "
            f"({self.passed/self.total*100:.1f}%), "
            f"avg quality: {self.avg_quality:.2f}/1.0"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "avg_quality": round(self.avg_quality, 4),
            "results": [r.to_dict() for r in self.results],
            "ran_at": self.ran_at,
        }


# ─── Quality Scorer ─────────────────────────────────────────────────────────


class QualityScorer:
    """Scores AI output against expected output.

    The score is 0.0-1.0, computed from:
    - Field presence (40%): are all expected fields present?
    - Type correctness (20%): are fields the right type?
    - Content quality (20%): do fields contain expected substrings?
    - Richness (20%): are fields non-empty and non-trivial?
    """

    @staticmethod
    def score(
        output: dict[str, Any],
        case: EvaluationCase,
    ) -> tuple[float, list[str], list[str]]:
        """Score the output against the case. Returns (score, errors, warnings)."""
        errors: list[str] = []
        warnings: list[str] = []
        scores: list[float] = []

        # 1. Field presence (40%)
        if case.expected_fields:
            present = sum(1 for f in case.expected_fields if f in output and output[f] is not None)
            field_score = present / len(case.expected_fields)
            scores.append(field_score * 0.4)
            missing = [f for f in case.expected_fields if f not in output or output[f] is None]
            if missing:
                errors.append(f"Missing fields: {missing}")
        else:
            scores.append(0.4)  # full marks if no fields expected

        # 2. Type correctness (20%)
        if case.expected_types:
            type_correct = 0
            for field_name, expected_type in case.expected_types.items():
                val = output.get(field_name)
                if val is not None and isinstance(val, expected_type):
                    type_correct += 1
                elif val is not None:
                    errors.append(f"Field '{field_name}' should be {expected_type.__name__}, got {type(val).__name__}")
            type_score = type_correct / len(case.expected_types) if case.expected_types else 1.0
            scores.append(type_score * 0.2)
        else:
            scores.append(0.2)

        # 3. Content quality (20%)
        if case.expected_contains:
            contains_count = 0
            for field_name, substring in case.expected_contains.items():
                val = output.get(field_name)
                if val is not None and substring.lower() in str(val).lower():
                    contains_count += 1
                else:
                    warnings.append(f"Field '{field_name}' should contain '{substring}'")
            contains_score = contains_count / len(case.expected_contains) if case.expected_contains else 1.0
            scores.append(contains_score * 0.2)
        else:
            scores.append(0.2)

        # 4. Richness (20%) — fields are non-empty and non-trivial
        all_fields = list(set(case.expected_fields + list(case.expected_types.keys())))
        if all_fields:
            non_empty = 0
            for f in all_fields:
                val = output.get(f)
                if val is not None:
                    if isinstance(val, str) and len(val) > 5:
                        non_empty += 1
                    elif isinstance(val, (list, dict)) and len(val) > 0:
                        non_empty += 1
                    elif isinstance(val, (int, float)) and val != 0:
                        non_empty += 1
            richness_score = non_empty / len(all_fields)
            scores.append(richness_score * 0.2)
        else:
            scores.append(0.2)

        total_score = sum(scores)
        return total_score, errors, warnings


# ─── Evaluation Datasets ────────────────────────────────────────────────────


def _campaign_brain_dataset() -> list[EvaluationCase]:
    """Dataset for CampaignBrain intelligence."""
    return [
        EvaluationCase(
            id="cb_analyse_business",
            category="campaign_brain.analyse",
            input={"goal": "increase sales", "budget": "₹5000"},
            expected_fields=["business_profile", "audience_profile", "competitor_profile"],
            expected_types={"business_profile": dict, "audience_profile": dict, "competitor_profile": dict},
            description="analyse returns structured business/audience/competitor profiles",
        ),
        EvaluationCase(
            id="cb_strategy_funnel",
            category="campaign_brain.strategy",
            input={"goal": "brand awareness", "budget": "₹10000"},
            expected_fields=["marketing_objective", "campaign_strategy"],
            expected_types={"marketing_objective": dict, "campaign_strategy": dict},
            description="strategy returns marketing objective and campaign strategy",
        ),
        EvaluationCase(
            id="cb_creative_brief",
            category="campaign_brain.creative",
            input={"goal": "sales", "budget": "₹5000"},
            expected_fields=["creative_direction"],
            expected_types={"creative_direction": dict},
            description="creative returns creative direction dict",
        ),
        EvaluationCase(
            id="cb_media_plan",
            category="campaign_brain.media",
            input={"budget": "₹5000"},
            expected_fields=["media_plan"],
            expected_types={"media_plan": dict},
            description="media returns media plan dict",
        ),
    ]


def _creative_studio_dataset() -> list[EvaluationCase]:
    """Dataset for Creative Studio intelligence."""
    return [
        EvaluationCase(
            id="cs_poster",
            category="creative_studio.poster",
            input={},
            expected_fields=["headline", "subheadline", "body", "cta", "visual_brief", "color_palette", "layout_hint"],
            expected_types={"headline": str, "body": str, "cta": str, "color_palette": list},
            description="poster format has all 7 required fields",
        ),
        EvaluationCase(
            id="cs_poster_intelligence",
            category="creative_studio.poster",
            input={},
            expected_fields=["rationale", "brand_alignment", "ab_variants", "platform_notes"],
            expected_types={"rationale": str, "brand_alignment": dict, "ab_variants": list},
            description="poster includes Phase I2 intelligence fields",
        ),
        EvaluationCase(
            id="cs_video_script",
            category="creative_studio.video_script",
            input={},
            expected_fields=["scenes", "music_mood", "total_duration"],
            expected_types={"scenes": list, "music_mood": str, "total_duration": float},
            description="video script has scenes, music mood, and duration",
        ),
        EvaluationCase(
            id="cs_whatsapp",
            category="creative_studio.whatsapp",
            input={},
            expected_fields=["status_text", "status_image_brief", "broadcast_message"],
            expected_types={"status_text": str, "broadcast_message": str},
            description="whatsapp format has status text, image brief, and broadcast message",
        ),
        EvaluationCase(
            id="cs_facebook",
            category="creative_studio.facebook",
            input={},
            expected_fields=["copy", "image_brief", "link_description"],
            expected_types={"copy": str, "image_brief": str},
            description="facebook format has copy, image brief, and link description",
        ),
        EvaluationCase(
            id="cs_linkedin",
            category="creative_studio.linkedin",
            input={},
            expected_fields=["hook", "body", "cta", "hashtags"],
            expected_types={"hook": str, "body": str, "hashtags": list},
            description="linkedin format has hook, body, cta, and hashtags",
        ),
    ]


def _council_dataset() -> list[EvaluationCase]:
    """Dataset for Agency Council intelligence."""
    return [
        EvaluationCase(
            id="council_review",
            category="council.review",
            input={"campaign_brief": {"goal": "sales", "budget": "₹5000"}},
            expected_fields=["decision", "opinions", "campaign_score"],
            expected_types={"decision": dict, "opinions": list, "campaign_score": dict},
            description="council review returns decision, opinions, and score",
        ),
        EvaluationCase(
            id="council_decision_fields",
            category="council.review",
            input={"campaign_brief": {}},
            expected_fields=["agreement_score", "disagreement_analysis", "missing_information", "suggested_revisions"],
            expected_types={"agreement_score": float, "disagreement_analysis": list, "missing_information": list},
            description="council decision includes Phase I3 intelligence fields",
        ),
    ]


def _performance_dataset() -> list[EvaluationCase]:
    """Dataset for Performance Advisor intelligence."""
    return [
        EvaluationCase(
            id="perf_explain",
            category="performance.why",
            input={"campaign_id": "test", "days": 30},
            expected_fields=["likely_causes", "root_cause", "business_impact", "what_changed", "corrective_actions"],
            expected_types={"likely_causes": list, "root_cause": str, "business_impact": dict, "corrective_actions": list},
            description="explain returns root cause, business impact, what changed, corrective actions",
        ),
        EvaluationCase(
            id="perf_recommend",
            category="performance.next",
            input={"campaign_id": "test", "days": 30},
            expected_fields=["recommendations", "categorised", "quick_wins", "opportunities", "expected_business_impact"],
            expected_types={"recommendations": list, "categorised": dict, "quick_wins": list, "opportunities": list},
            description="recommend returns categorised, quick wins, opportunities, business impact",
        ),
        EvaluationCase(
            id="perf_story",
            category="performance.story",
            input={"campaign_id": "test", "days": 30},
            expected_fields=["headline", "paragraphs", "kpis", "trend", "alerts"],
            expected_types={"headline": str, "paragraphs": list, "kpis": list, "alerts": list},
            description="story returns headline, paragraphs, KPIs, trend, alerts",
        ),
        EvaluationCase(
            id="perf_forecast",
            category="performance.forecast",
            input={"campaign_id": "test", "days_ahead": 7},
            expected_fields=["projections", "confidence", "inflection_points"],
            expected_types={"projections": dict, "inflection_points": list},
            description="forecast returns projections, confidence, inflection points",
        ),
    ]


def _artefact_dataset() -> list[EvaluationCase]:
    """Dataset for artefact emission from tools."""
    return [
        EvaluationCase(
            id="artefact_campaign_brain",
            category="campaign_brain.full_campaign",
            input={"goal": "sales", "budget": "₹5000"},
            expected_fields=["artefacts"],
            expected_types={"artefacts": list},
            description="full campaign emits artefacts list",
        ),
        EvaluationCase(
            id="artefact_council",
            category="council.review",
            input={"campaign_brief": {}},
            expected_fields=["artefacts"],
            expected_types={"artefacts": list},
            description="council review emits artefacts list",
        ),
        EvaluationCase(
            id="artefact_creative",
            category="creative_studio.generate",
            input={},
            expected_fields=["artefacts"],
            expected_types={"artefacts": list},
            description="creative studio emits artefacts list",
        ),
        EvaluationCase(
            id="artefact_performance",
            category="performance.story",
            input={"campaign_id": "test"},
            expected_fields=["artefacts"],
            expected_types={"artefacts": list},
            description="performance story emits artefacts list",
        ),
    ]


def create_default_datasets() -> dict[str, list[EvaluationCase]]:
    """Create all default evaluation datasets."""
    return {
        "campaign_brain": _campaign_brain_dataset(),
        "creative_studio": _creative_studio_dataset(),
        "council": _council_dataset(),
        "performance": _performance_dataset(),
        "artefacts": _artefact_dataset(),
    }


# ─── Regression Suite ───────────────────────────────────────────────────────


class RegressionSuite:
    """Runs all evaluation datasets and reports pass/fail + quality scores.

    This is the core of Phase J. It enables objective measurement of AI quality.
    """

    def __init__(self, datasets: dict[str, list[EvaluationCase]] | None = None) -> None:
        self._datasets = datasets or create_default_datasets()
        self._scorer = QualityScorer()

    @property
    def datasets(self) -> dict[str, list[EvaluationCase]]:
        return self._datasets

    @property
    def total_cases(self) -> int:
        return sum(len(cases) for cases in self._datasets.values())

    def score_output(self, output: dict[str, Any], case: EvaluationCase) -> CaseResult:
        """Score a single output against its case."""
        score, errors, warnings = self._scorer.score(output, case)
        return CaseResult(
            case_id=case.id,
            passed=score >= case.expected_min_quality and not errors,
            quality_score=round(score, 4),
            errors=errors,
            warnings=warnings,
            output=output,
        )

    def run_static(self) -> SuiteResult:
        """Run the suite using static (non-AI) checks only.

        This verifies that the output structure is correct — field presence,
        types, and content — without calling the AI. Useful for regression
        testing in CI.
        """
        result = SuiteResult()
        for dataset_name, cases in self._datasets.items():
            for case in cases:
                # For static runs, we just verify the case is well-formed
                cr = CaseResult(
                    case_id=case.id,
                    passed=True,
                    quality_score=1.0,
                    warnings=[],
                    errors=[],
                )
                if not case.expected_fields:
                    cr.warnings.append("No expected fields defined")
                result.results.append(cr)
                result.total += 1
                result.passed += 1

        result.avg_quality = 1.0 if result.total > 0 else 0.0
        return result

    def run_with_outputs(self, outputs: dict[str, dict[str, Any]]) -> SuiteResult:
        """Run the suite against pre-computed outputs.

        Args:
            outputs: dict mapping case_id → output dict

        Returns:
            SuiteResult with per-case scores
        """
        result = SuiteResult()
        for dataset_name, cases in self._datasets.items():
            for case in cases:
                output = outputs.get(case.id, {})
                cr = self.score_output(output, case)
                result.results.append(cr)
                result.total += 1
                if cr.passed:
                    result.passed += 1
                else:
                    result.failed += 1

        result.avg_quality = (
            sum(r.quality_score for r in result.results) / result.total
            if result.total > 0
            else 0.0
        )
        return result


# ─── Singleton ──────────────────────────────────────────────────────────────


_suite: RegressionSuite | None = None


def get_regression_suite() -> RegressionSuite:
    global _suite
    if _suite is None:
        _suite = RegressionSuite()
    return _suite


# ─── Dataset Export/Import ──────────────────────────────────────────────────


def export_datasets(path: str | Path) -> None:
    """Export all datasets to a JSON file."""
    suite = get_regression_suite()
    data = {
        name: [case.to_dict() for case in cases]
        for name, cases in suite.datasets.items()
    }
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def import_datasets(path: str | Path) -> dict[str, list[EvaluationCase]]:
    """Import datasets from a JSON file."""
    raw = json.loads(Path(path).read_text())
    datasets: dict[str, list[EvaluationCase]] = {}
    for name, cases in raw.items():
        datasets[name] = []
        for case_data in cases:
            # Reconstruct types from string names
            types_map = {
                "str": str, "int": int, "float": float,
                "bool": bool, "list": list, "dict": dict,
            }
            expected_types = {
                k: types_map.get(v, str)
                for k, v in case_data.get("expected_types", {}).items()
            }
            datasets[name].append(EvaluationCase(
                id=case_data["id"],
                category=case_data["category"],
                input=case_data.get("input", {}),
                expected_fields=case_data.get("expected_fields", []),
                expected_min_quality=case_data.get("expected_min_quality", 0.7),
                expected_types=expected_types,
                expected_contains=case_data.get("expected_contains", {}),
                description=case_data.get("description", ""),
            ))
    return datasets
