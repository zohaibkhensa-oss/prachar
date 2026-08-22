from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any

import redis
from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from ..config import get_settings
from .budget import BudgetGuard
from .cache import Cache, ttl_for
from .json_utils import extract_json
from .observability import estimate_cost, log_ai_request, new_request_id
from .safety import check_output_for_leaks, detect_injection, sanitize_input
from .tiering import Tier, pick_model

logger = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    pass


class ProviderError(Exception):
    """Raised when a provider call fails after all retries."""

    pass


class Completion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    json_value: dict[str, Any] | None = None
    tokens_used: int = 0
    model: str
    cached: bool = False
    provider: str = ""
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    request_id: str = ""
    confidence: float = 0.0  # 0.0-1.0, estimated confidence in response quality


class AIGateway:
    def __init__(
        self,
        cache: Cache | None = None,
        budget: BudgetGuard | None = None,
        redis_client: redis.Redis | None = None,
    ) -> None:
        self._redis = redis_client
        self.cache = cache if cache is not None else Cache(self._redis)
        self.budget = budget if budget is not None else BudgetGuard(self._redis)

    def _stub_mode(self) -> bool:
        s = get_settings()
        return not (s.anthropic_api_key.strip() or s.openai_api_key.strip() or s.groq_api_key.strip())

    async def async_complete(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> Completion:
        """Async wrapper around complete() — runs the sync LLM call in a thread.

        Use this from async code (FastAPI routes, runtime, tools):
            completion = await gateway.async_complete(prompt=..., tier=..., ...)
        """
        import asyncio
        return await asyncio.to_thread(self.complete, prompt, **kwargs)

    def complete(
        self,
        prompt: str,
        *,
        tier: Tier = Tier.small,
        schema: dict[str, Any] | None = None,
        task: str = "generic",
        tenant_id: uuid.UUID,
        plan: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        retries: int = 1,
        user_input: str | None = None,
        prompt_version: str = "",
        campaign_id: str = "",
    ) -> Completion:
        # ─── Safety: check for prompt injection ───────────────────────────
        if user_input:
            risk = detect_injection(user_input)
            if risk.is_dangerous:
                logger.warning(
                    "prompt injection blocked: patterns=%s input_preview=%.100s",
                    risk.detected_patterns,
                    user_input,
                )
                from .safety import BLOCKED_RESPONSE

                return Completion(
                    text=BLOCKED_RESPONSE,
                    tokens_used=0,
                    model="safety-blocked",
                    provider="safety",
                    confidence=0.0,
                    request_id=new_request_id(),
                )

        request_id = new_request_id()
        t0 = time.monotonic()
        model = pick_model(tier)
        key = self.cache.key(model, prompt, schema)

        cached = self.cache.get(key)
        if cached is not None:
            try:
                data = json.loads(cached)
                comp = Completion.model_validate(data)
                comp.cached = True
                comp.latency_ms = round((time.monotonic() - t0) * 1000, 2)
                comp.request_id = request_id
                # Log cache hit
                log_ai_request(
                    request_id=request_id,
                    tenant_id=str(tenant_id),
                    task=task,
                    model=model,
                    provider="cache",
                    latency_ms=comp.latency_ms,
                    tokens_used=comp.tokens_used,
                    cached=True,
                    success=True,
                    prompt_version=prompt_version,
                    campaign_id=campaign_id,
                )
                return comp
            except Exception:
                logger.debug("cache parse failed, recomputing", exc_info=True)

        if not self.budget.check_and_reserve(tenant_id, max_tokens, plan):
            log_ai_request(
                request_id=request_id,
                tenant_id=str(tenant_id),
                task=task,
                model=model,
                provider="none",
                latency_ms=round((time.monotonic() - t0) * 1000, 2),
                tokens_used=0,
                success=False,
                failure_reason="budget_exceeded",
                prompt_version=prompt_version,
                campaign_id=campaign_id,
            )
            raise BudgetExceeded(f"budget exceeded for tenant {tenant_id} plan={plan}")

        if self._stub_mode():
            comp = self._stub_complete(prompt, model, schema, task)
        else:
            try:
                comp = self._provider_complete(
                    prompt=prompt,
                    model=model,
                    schema=schema,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    retries=retries,
                )
            except Exception as exc:
                latency_ms = round((time.monotonic() - t0) * 1000, 2)
                log_ai_request(
                    request_id=request_id,
                    tenant_id=str(tenant_id),
                    task=task,
                    model=model,
                    provider="failed",
                    latency_ms=latency_ms,
                    tokens_used=0,
                    success=False,
                    failure_reason=str(exc)[:500],
                    prompt_version=prompt_version,
                    campaign_id=campaign_id,
                )
                raise

        # ─── Post-processing: JSON extraction & safety checks ─────────────
        # If schema was requested but json_value is None, try extracting from text
        if schema is not None and comp.json_value is None and comp.text:
            extracted = extract_json(comp.text)
            if extracted is not None and isinstance(extracted, dict):
                comp.json_value = extracted
                try:
                    self._validate_json(schema, extracted)
                except RuntimeError:
                    # Schema validation failed on extracted JSON — leave as text
                    comp.json_value = None

        # Check output for system prompt leaks
        if user_input and comp.text:
            if not check_output_for_leaks(comp.text):
                logger.warning("output leak detected for request %s", request_id)
                comp.text = "I can only help with CURV AI platform questions and advertising expertise."
                comp.confidence = 0.0

        # Estimate confidence based on response quality signals
        if not comp.confidence:
            comp.confidence = self._estimate_confidence(comp, schema)

        # Fill in observability fields
        comp.latency_ms = round((time.monotonic() - t0) * 1000, 2)
        comp.cost_usd = estimate_cost(comp.model, comp.tokens_used)
        comp.request_id = request_id

        self.budget.record_usage(tenant_id, comp.tokens_used or max_tokens, plan)
        self.cache.set(key, comp.model_dump_json(), ttl_for(task))

        # Log successful request
        log_ai_request(
            request_id=request_id,
            tenant_id=str(tenant_id),
            task=task,
            model=comp.model,
            provider=comp.provider,
            latency_ms=comp.latency_ms,
            tokens_used=comp.tokens_used,
            cost_usd=comp.cost_usd,
            cached=False,
            success=True,
            prompt_version=prompt_version,
            campaign_id=campaign_id,
        )

        return comp

    @staticmethod
    def _estimate_confidence(comp: Completion, schema: dict[str, Any] | None) -> float:
        """Estimate confidence in the response quality (0.0-1.0)."""
        score = 0.5  # Base confidence

        # Higher confidence if schema was requested and validated
        if schema is not None and comp.json_value is not None:
            score += 0.3

        # Lower confidence if response is very short (may be incomplete)
        if len(comp.text) < 20:
            score -= 0.2

        # Lower confidence if response contains uncertainty markers
        uncertainty_markers = ["i don't know", "i'm not sure", "i cannot", "unable to", "i don't have"]
        text_lower = comp.text.lower()
        if any(marker in text_lower for marker in uncertainty_markers):
            score -= 0.1

        # Higher confidence if response is substantive
        if len(comp.text) > 100:
            score += 0.1

        # Lower confidence if stub mode
        if comp.model == "stub":
            score = 0.1

        return max(0.0, min(1.0, round(score, 2)))

    # ----- stub -----
    def _stub_complete(
        self,
        prompt: str,
        model: str,
        schema: dict[str, Any] | None,
        task: str = "generic",
    ) -> Completion:
        # Special stub for chat — return a helpful message
        if task == "chat":
            return Completion(
                text=(
                    "Hey! I'm CURV AI running in demo mode. To get full AI responses, "
                    "set the ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file. "
                    "In the meantime, I can still help you navigate the platform — "
                    "try asking me to take you to campaigns, analytics, or creative AI!"
                ),
                tokens_used=64,
                model="stub",
                provider="stub",
            )
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        text = f"[stub] {digest}"
        json_value: dict[str, Any] | None = None
        if schema is not None:
            json_value = self._stub_json(schema, digest)
        return Completion(text=text, json_value=json_value, tokens_used=64, model="stub", provider="stub")

    @staticmethod
    def _stub_json(schema: dict[str, Any], digest: str) -> dict[str, Any]:
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        out: dict[str, Any] = {}
        for name, spec in props.items():
            t = spec.get("type", "string") if isinstance(spec, dict) else "string"
            if t == "string":
                out[name] = f"stub-{name}-{digest[:8]}"
            elif t in ("integer", "number"):
                out[name] = int(digest[:8], 16) % 100
            elif t == "boolean":
                out[name] = bool(int(digest[0], 16) % 2)
            elif t == "array":
                out[name] = []
            elif t == "object":
                out[name] = {}
            else:
                out[name] = None
        return out

    # ----- provider -----
    def _provider_complete(
        self,
        *,
        prompt: str,
        model: str,
        schema: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
        retries: int,
    ) -> Completion:
        settings = get_settings()
        primary = settings.ai_default_provider.lower()
        # Build fallback chain: try primary, then any other configured provider
        all_providers = ["groq", "gemini", "anthropic", "openai"]
        if primary in all_providers:
            all_providers.remove(primary)
        fallback_chain = [primary] + all_providers

        # Only try providers that have API keys configured
        s = get_settings()
        configured = []
        for p in fallback_chain:
            if p == "groq" and s.groq_api_key.strip():
                configured.append(p)
            elif p == "gemini" and s.gemini_api_key.strip():
                configured.append(p)
            elif p == "anthropic" and s.anthropic_api_key.strip():
                configured.append(p)
            elif p == "openai" and s.openai_api_key.strip():
                configured.append(p)

        if not configured:
            # No keys but not in stub mode (shouldn't happen) — return stub
            return self._stub_complete(prompt, model, schema)

        last_err: Exception | None = None
        feedback: str | None = None
        for provider in configured:
            try:
                return self._call_provider(
                    provider=provider,
                    prompt=prompt,
                    model=self._pick_model_for_provider(provider, model),
                    schema=schema,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    feedback=feedback,
                )
            except Exception as e:
                logger.warning("provider %s failed: %s", provider, e)
                last_err = e
                feedback = f"Previous attempt failed: {e}"

        raise RuntimeError(f"all providers failed: {last_err}") from last_err

    @staticmethod
    def _pick_model_for_provider(provider: str, model: str) -> str:
        """Map a logical model to the correct model name for each provider.
        
        Handles cross-provider fallback: when the primary provider fails and we
        fall back to another, the model name from the primary may not exist on
        the fallback provider. We detect this and map to the correct model.
        """
        s = get_settings()
        
        # Detect if the model name belongs to a different provider and remap
        is_gemini_model = "gemini" in model
        is_groq_model = "llama" in model or "mixtral" in model or "gemma" in model
        is_anthropic_model = "claude" in model
        is_openai_model = "gpt" in model
        
        if provider == "groq":
            # If model is already a Groq model, use it directly
            if is_groq_model:
                return model
            # Map non-Groq models to Groq equivalents
            if "pro" in model or "large" in model or "sonnet" in model or "gpt-4o" == model:
                return s.ai_large_model if "llama" in s.ai_large_model else "llama-3.3-70b-versatile"
            # Small/default models
            return s.ai_small_model if "llama" in s.ai_small_model else "llama-3.1-8b-instant"
            
        if provider == "gemini":
            # If model is already a Gemini model, use it directly
            if is_gemini_model:
                return model
            # Map non-Gemini models to Gemini equivalents
            if "70b" in model or "large" in model or "sonnet" in model or "gpt-4o" == model:
                return s.ai_large_model if "gemini" in s.ai_large_model else "gemini-pro-latest"
            return s.ai_small_model if "gemini" in s.ai_small_model else "gemini-flash-latest"
            
        if provider == "openai":
            if is_openai_model:
                return model
            if "70b" in model or "large" in model or "pro" in model or "sonnet" in model:
                return "gpt-4o"
            return "gpt-4o-mini"
            
        if provider == "anthropic":
            if is_anthropic_model:
                return model
            if "70b" in model or "large" in model or "pro" in model:
                return "claude-3-5-sonnet-20241022"
            return "claude-3-5-haiku-20241022"
            
        return model

    def _call_provider(
        self,
        *,
        provider: str,
        prompt: str,
        model: str,
        schema: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
        feedback: str | None,
    ) -> Completion:
        if provider == "anthropic":
            return self._call_anthropic(prompt, model, schema, max_tokens, temperature, feedback)
        if provider == "groq":
            return self._call_groq(prompt, model, schema, max_tokens, temperature, feedback)
        if provider == "gemini":
            return self._call_gemini(prompt, model, schema, max_tokens, temperature, feedback)
        return self._call_openai(prompt, model, schema, max_tokens, temperature, feedback)

    def _call_groq(
        self,
        prompt: str,
        model: str,
        schema: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
        feedback: str | None,
    ) -> Completion:
        """Call Groq API (OpenAI-compatible)."""
        import openai as openai_lib

        s = get_settings()
        client = openai_lib.OpenAI(
            api_key=s.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=30.0,
            max_retries=1,  # Don't retry 429s internally — let fallback chain handle it
        )
        full_prompt = prompt if not feedback else f"{prompt}\n\n[feedback] {feedback}"
        if schema is not None:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": f"Return JSON matching this schema: {json.dumps(schema)}"},
                    {"role": "user", "content": full_prompt},
                ],
            )
            content = resp.choices[0].message.content or "{}"
            # Use universal JSON extractor (handles markdown fences, prose, etc.)
            json_value = extract_json(content)
            if json_value is None or not isinstance(json_value, dict):
                raise RuntimeError(f"Groq returned non-JSON despite json_object format: {content[:200]}")
            self._validate_json(schema, json_value)
            tokens = resp.usage.total_tokens if resp.usage else 0
            return Completion(text=content, json_value=json_value, tokens_used=tokens, model=model, provider="groq")
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": full_prompt}],
        )
        text = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return Completion(text=text, tokens_used=tokens, model=model, provider="groq")

    def _call_gemini(
        self,
        prompt: str,
        model: str,
        schema: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
        feedback: str | None,
    ) -> Completion:
        """Call Google Gemini API (OpenAI-compatible endpoint)."""
        import openai as openai_lib

        s = get_settings()
        client = openai_lib.OpenAI(
            api_key=s.gemini_api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            timeout=30.0,
            max_retries=1,
        )
        full_prompt = prompt if not feedback else f"{prompt}\n\n[feedback] {feedback}"
        if schema is not None:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": f"Return JSON matching this schema: {json.dumps(schema)}"},
                    {"role": "user", "content": full_prompt},
                ],
            )
            content = resp.choices[0].message.content or "{}"
            json_value = extract_json(content)
            if json_value is None or not isinstance(json_value, dict):
                raise RuntimeError(f"Gemini returned non-JSON despite json_object format: {content[:200]}")
            self._validate_json(schema, json_value)
            tokens = resp.usage.total_tokens if resp.usage else 0
            return Completion(text=content, json_value=json_value, tokens_used=tokens, model=model, provider="gemini")
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": full_prompt}],
        )
        text = resp.choices[0].message.content or ""
        if not text.strip():
            raise RuntimeError("Gemini returned empty content")
        tokens = resp.usage.total_tokens if resp.usage else 0
        return Completion(text=text, tokens_used=tokens, model=model, provider="gemini")

    def _call_anthropic(
        self,
        prompt: str,
        model: str,
        schema: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
        feedback: str | None,
    ) -> Completion:
        import anthropic

        client = anthropic.Anthropic(
            api_key=get_settings().anthropic_api_key,
            timeout=60.0,
        )
        full_prompt = prompt if not feedback else f"{prompt}\n\n[feedback] {feedback}"
        if schema is not None:
            return self._anthropic_tool_json(client, model, full_prompt, schema, max_tokens, temperature)
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": full_prompt}],
        )
        text = "".join(block.text for block in resp.content if hasattr(block, "text"))
        return Completion(
            text=text,
            tokens_used=resp.usage.input_tokens + resp.usage.output_tokens,
            model=model,
            provider="anthropic",
        )

    def _anthropic_tool_json(
        self,
        client,
        model: str,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        temperature: float,
    ) -> Completion:
        tool = {
            "name": "emit",
            "description": "Emit the structured result.",
            "input_schema": schema,
        }
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=[tool],
            tool_choice={"type": "tool", "name": "emit"},
            messages=[{"role": "user", "content": prompt}],
        )
        json_value: dict[str, Any] | None = None
        text_parts: list[str] = []
        for block in resp.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "emit":
                json_value = block.input
        if json_value is None:
            raise RuntimeError("anthropic did not return tool_use")
        self._validate_json(schema, json_value)
        return Completion(
            text="\n".join(text_parts),
            json_value=json_value,
            tokens_used=resp.usage.input_tokens + resp.usage.output_tokens,
            model=model,
            provider="anthropic",
        )

    def _call_openai(
        self,
        prompt: str,
        model: str,
        schema: dict[str, Any] | None,
        max_tokens: int,
        temperature: float,
        feedback: str | None,
    ) -> Completion:
        import openai

        client = openai.OpenAI(
            api_key=get_settings().openai_api_key,
            timeout=60.0,
        )
        full_prompt = prompt if not feedback else f"{prompt}\n\n[feedback] {feedback}"
        if schema is not None:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": f"Return JSON matching this schema: {json.dumps(schema)}"},
                    {"role": "user", "content": full_prompt},
                ],
            )
            content = resp.choices[0].message.content or "{}"
            # Use universal JSON extractor
            json_value = extract_json(content)
            if json_value is None or not isinstance(json_value, dict):
                raise RuntimeError(f"OpenAI returned non-JSON despite json_object format: {content[:200]}")
            self._validate_json(schema, json_value)
            tokens = resp.usage.total_tokens if resp.usage else 0
            return Completion(text=content, json_value=json_value, tokens_used=tokens, model=model, provider="openai")
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": full_prompt}],
        )
        text = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return Completion(text=text, tokens_used=tokens, model=model, provider="openai")

    @staticmethod
    def _validate_json(schema: dict[str, Any], value: dict[str, Any]) -> None:
        props = schema.get("properties", {})
        required = schema.get("required", [])
        fields: dict[str, Any] = {}
        for name, spec in props.items():
            t = spec.get("type", "string") if isinstance(spec, dict) else "string"
            py: Any = str
            if t == "integer":
                py = int
            elif t == "number":
                py = float
            elif t == "boolean":
                py = bool
            elif t == "array":
                py = list
            elif t == "object":
                py = dict
            default = ... if name in required else None
            fields[name] = (py | None, default)
        Model = create_model("SchemaModel", __config__=ConfigDict(extra="forbid"), **fields)
        try:
            Model.model_validate(value)
        except ValidationError as e:
            raise RuntimeError(f"schema validation failed: {e}") from e
