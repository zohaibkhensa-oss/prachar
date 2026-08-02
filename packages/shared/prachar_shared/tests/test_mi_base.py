"""Tests for the Marketing Intelligence Engine — base + business engine.

Run: pytest packages/shared/prachar_shared/tests/test_mi_base.py -v
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import Completion
from prachar_shared.marketing_intelligence import (
    BusinessIntelligenceEngine,
    BusinessProfile,
    EngineOutput,
    IntelligenceEngine,
    Recommendation,
)


# ─── Test doubles ───────────────────────────────────────────────────────────


class _StubGateway:
    """Stub AIGateway that returns canned Completions for deterministic tests."""

    def __init__(self, json_value: dict[str, Any] | None = None, text: str = "") -> None:
        self._json = json_value or {}
        self._text = text
        self.calls: list[dict[str, Any]] = []

    def complete(self, **kw: Any) -> Completion:
        self.calls.append(kw)
        return Completion(
            text=self._text or "[stub]",
            json_value=self._json,
            tokens_used=128,
            model="stub",
            provider="stub",
            latency_ms=5.0,
            cost_usd=0.001,
            request_id="test-req-001",
            confidence=0.7,
        )


# ─── Recommendation ─────────────────────────────────────────────────────────


class TestRecommendation:
    def test_default_fields(self) -> None:
        rec = Recommendation(title="Test", description="desc")
        assert rec.title == "Test"
        assert rec.confidence == 0.5
        assert rec.alternatives == []
        assert rec.risks == []

    def test_to_dict_roundtrip(self) -> None:
        rec = Recommendation(
            title="Use Instagram",
            description="Primary channel for Gen Z",
            confidence=0.8,
            business_rationale="High ROI",
            marketing_rationale="Audience presence",
            alternatives=["TikTok", "YouTube"],
            risks=["Algorithm changes"],
            expected_outcome="2x engagement",
            evidence=["2024 data"],
            sources=["internal"],
        )
        d = rec.to_dict()
        assert d["title"] == "Use Instagram"
        assert d["confidence"] == 0.8
        assert "TikTok" in d["alternatives"]
        assert d["expected_outcome"] == "2x engagement"


# ─── EngineOutput ───────────────────────────────────────────────────────────


class TestEngineOutput:
    def test_defaults(self) -> None:
        out = EngineOutput(result={})
        assert out.result == {}
        assert out.confidence == 0.5
        assert out.recommendations == []
        assert out.cost_usd == 0.0

    def test_to_dict(self) -> None:
        out = EngineOutput(
            result={"industry": "D2C coffee"},
            confidence=0.8,
            reasoning="Analyzed website",
            model="llama-3.3-70b",
            provider="groq",
            tokens_used=500,
            cost_usd=0.005,
        )
        d = out.to_dict()
        assert d["result"]["industry"] == "D2C coffee"
        assert d["confidence"] == 0.8
        assert d["model"] == "llama-3.3-70b"


# ─── IntelligenceEngine base class ──────────────────────────────────────────


class _DummyEngine(IntelligenceEngine):
    ENGINE_NAME = "dummy"
    PROMPT_VERSION = "1.0.0"

    def _build_prompt(self, **kw: Any) -> str:
        return f"Analyze: {kw}"

    def _build_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"answer": {"type": "string"}}}


class TestIntelligenceEngineBase:
    def test_run_calls_gateway_and_returns_output(self) -> None:
        gw = _StubGateway(json_value={"answer": "42", "confidence": 0.9, "reasoning": "deep thought"})
        engine = _DummyEngine(gateway=gw)
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency", foo="bar")

        assert out.result == {"answer": "42", "confidence": 0.9, "reasoning": "deep thought"}
        assert out.confidence == 0.9
        assert out.model == "stub"
        assert out.provider == "stub"
        assert out.tokens_used == 128
        assert out.cost_usd == 0.001
        assert out.request_id == "test-req-001"
        assert out.prompt_version == "dummy_v1.0.0"
        assert out.latency_ms > 0
        # Verify the gateway was called with the right task
        assert len(gw.calls) == 1
        assert gw.calls[0]["task"] == "dummy"
        assert gw.calls[0]["prompt_version"] == "dummy_v1.0.0"

    def test_run_populates_versioning_fields(self) -> None:
        """Phase 2: every output must be versioned."""
        gw = _StubGateway(json_value={"answer": "42", "confidence": 0.9})
        engine = _DummyEngine(gateway=gw)
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency")

        assert out.schema_version == "1.0.0"  # default from base
        assert out.engine_version == "1.0.0"
        assert out.prompt_version == "dummy_v1.0.0"
        assert out.model_version == "stub:stub"  # provider:model
        assert out.generated_by == "dummy"
        assert out.created_at != ""  # ISO timestamp
        assert "T" in out.created_at  # ISO format check

    def test_run_populates_versioning_on_failure(self) -> None:
        """Versioning should be populated even when the engine fails."""
        class _FailGateway:
            def complete(self, **kw: Any) -> Completion:
                raise RuntimeError("API down")

        engine = _DummyEngine(gateway=_FailGateway())
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency")
        # On failure, versioning reflects the engine that attempted the call
        assert out.generated_by == "dummy"
        assert out.engine_version == "1.0.0"
        assert out.confidence == 0.0

    def test_run_handles_gateway_failure(self) -> None:
        class _FailGateway:
            def complete(self, **kw: Any) -> Completion:
                raise RuntimeError("API down")

        engine = _DummyEngine(gateway=_FailGateway())
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency")
        assert out.confidence == 0.0
        assert "Engine failed" in out.reasoning
        assert out.model == "error"

    def test_lazy_gateway_init(self) -> None:
        engine = _DummyEngine()
        # Accessing gateway property should not raise (creates AIGateway)
        gw = engine.gateway
        assert gw is not None

    def test_extract_recommendations(self) -> None:
        engine = _DummyEngine()
        result = {
            "recommendations": [
                {
                    "title": "Rec 1",
                    "description": "First",
                    "confidence": 0.8,
                    "business_rationale": "br",
                    "marketing_rationale": "mr",
                    "alternatives": ["alt"],
                    "risks": ["risk"],
                    "expected_outcome": "good",
                    "evidence": ["e"],
                    "sources": ["s"],
                },
                {"title": "Rec 2", "description": "Second"},
                "not a dict",  # should be skipped
            ]
        }
        recs = engine._extract_recommendations(result)
        assert len(recs) == 2
        assert recs[0].title == "Rec 1"
        assert recs[0].confidence == 0.8
        assert recs[1].title == "Rec 2"

    def test_extract_recommendations_empty(self) -> None:
        engine = _DummyEngine()
        assert engine._extract_recommendations({}) == []
        assert engine._extract_recommendations({"recommendations": "not a list"}) == []

    def test_format_input_summary(self) -> None:
        s = IntelligenceEngine._format_input_summary(name="Acme", budget="₹5L", empty="", none_val=None)
        assert "name: Acme" in s
        assert "budget: ₹5L" in s
        assert "empty" not in s
        assert "none_val" not in s


# ─── BusinessIntelligenceEngine ─────────────────────────────────────────────


class TestBusinessIntelligenceEngine:
    def _stub_result(self) -> dict[str, Any]:
        return {
            "industry": "D2C Premium Coffee",
            "sub_industry": "Specialty Coffee Roasters",
            "business_model": "D2C",
            "products_services": [
                {"name": "Single Origin Beans", "positioning": "Premium", "price_point": "₹800/250g"}
            ],
            "usp": "Farm-to-cup traceability with direct trade",
            "pricing_model": "premium",
            "price_range": "₹500-2000",
            "customer_type": "Urban millennials, 25-40, high income",
            "business_maturity": "growth",
            "market_position": "challenger",
            "seasonality": {"peak_periods": ["Winter", "Diwali"], "off_periods": ["Monsoon"]},
            "strengths": ["Direct trade relationships", "Brand storytelling"],
            "weaknesses": ["Limited distribution", "High price point"],
            "opportunities": ["Tier-2 expansion", "Subscription model"],
            "threats": ["International brands entering", "Coffee price volatility"],
            "target_market_size": "₹2,000 Cr premium coffee",
            "competitive_landscape": "Blue Tokai, Third Wave, Sleepy Owl",
            "regulatory_considerations": ["FSSAI compliance"],
            "reasoning": "Analyzed website, product range, and pricing.",
            "confidence": 0.75,
            "recommendations": [
                {
                    "title": "Launch subscription model",
                    "description": "Monthly bean delivery",
                    "confidence": 0.8,
                    "business_rationale": "Recurring revenue",
                    "marketing_rationale": "Retention focus",
                    "alternatives": ["One-time purchase"],
                    "risks": ["Churn"],
                    "expected_outcome": "30% revenue increase",
                    "evidence": ["Industry data"],
                    "sources": ["internal"],
                }
            ],
        }

    def test_engine_name_and_version(self) -> None:
        engine = BusinessIntelligenceEngine()
        assert engine.ENGINE_NAME == "business_intelligence"
        assert engine.PROMPT_VERSION == "3.0.0"

    def test_build_prompt_contains_business_info(self) -> None:
        engine = BusinessIntelligenceEngine()
        prompt = engine._build_prompt(
            business_name="Acme Coffee",
            website="acme.com",
            category="Coffee",
            description="Premium D2C coffee",
        )
        assert "Acme Coffee" in prompt
        assert "acme.com" in prompt
        assert "McKinsey" in prompt  # Role definition
        assert "USP" in prompt  # Analysis requirement

    def test_build_schema_has_required_fields(self) -> None:
        engine = BusinessIntelligenceEngine()
        schema = engine._build_schema()
        assert schema["type"] == "object"
        required = schema["required"]
        assert "industry" in required
        assert "business_model" in required
        assert "usp" in required
        assert "confidence" in required

    def test_run_returns_structured_output(self) -> None:
        gw = _StubGateway(json_value=self._stub_result())
        engine = BusinessIntelligenceEngine(gateway=gw)
        out = engine.run(
            tenant_id=uuid.uuid4(),
            plan="agency",
            business_name="Acme Coffee",
            website="acme.com",
        )
        assert out.result["industry"] == "D2C Premium Coffee"
        assert out.confidence == 0.75
        assert len(out.recommendations) == 1
        assert out.recommendations[0].title == "Launch subscription model"
        assert out.tokens_used == 128

    def test_to_profile_converts_output(self) -> None:
        gw = _StubGateway(json_value=self._stub_result())
        engine = BusinessIntelligenceEngine(gateway=gw)
        out = engine.run(tenant_id=uuid.uuid4(), plan="agency", business_name="Acme")
        profile = engine.to_profile(out)
        assert isinstance(profile, BusinessProfile)
        assert profile.industry == "D2C Premium Coffee"
        assert profile.business_model == "D2C"
        assert profile.usp == "Farm-to-cup traceability with direct trade"
        assert len(profile.strengths) == 2
        assert profile.seasonality["peak_periods"] == ["Winter", "Diwali"]

    def test_to_profile_handles_empty_result(self) -> None:
        engine = BusinessIntelligenceEngine()
        out = EngineOutput(result={})
        profile = engine.to_profile(out)
        assert profile.industry == ""
        assert profile.strengths == []
        assert profile.seasonality == {}

    def test_business_profile_to_dict(self) -> None:
        profile = BusinessProfile(industry="Tech", usp="Fast")
        d = profile.to_dict()
        assert d["industry"] == "Tech"
        assert d["usp"] == "Fast"
        assert d["strengths"] == []
