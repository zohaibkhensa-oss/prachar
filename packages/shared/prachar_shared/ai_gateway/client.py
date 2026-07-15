from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

import redis
from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from ..config import get_settings
from .budget import BudgetGuard
from .cache import Cache, ttl_for
from .tiering import Tier, pick_model

logger = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    pass


class Completion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    json_value: dict[str, Any] | None = None
    tokens_used: int = 0
    model: str
    cached: bool = False


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
    ) -> Completion:
        model = pick_model(tier)
        key = self.cache.key(model, prompt, schema)

        cached = self.cache.get(key)
        if cached is not None:
            try:
                data = json.loads(cached)
                comp = Completion.model_validate(data)
                comp.cached = True
                return comp
            except Exception:
                logger.debug("cache parse failed, recomputing", exc_info=True)

        if not self.budget.check_and_reserve(tenant_id, max_tokens, plan):
            raise BudgetExceeded(f"budget exceeded for tenant {tenant_id} plan={plan}")

        if self._stub_mode():
            comp = self._stub_complete(prompt, model, schema, task)
        else:
            comp = self._provider_complete(
                prompt=prompt,
                model=model,
                schema=schema,
                max_tokens=max_tokens,
                temperature=temperature,
                retries=retries,
            )

        self.budget.record_usage(tenant_id, comp.tokens_used or max_tokens, plan)
        self.cache.set(key, comp.model_dump_json(), ttl_for(task))
        return comp

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
                    "Hey! I'm PRACHAR AI running in demo mode. To get full AI responses, "
                    "set the ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file. "
                    "In the meantime, I can still help you navigate the platform — "
                    "try asking me to take you to campaigns, analytics, or creative AI!"
                ),
                tokens_used=64,
                model="stub",
            )
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        text = f"[stub] {digest}"
        json_value: dict[str, Any] | None = None
        if schema is not None:
            json_value = self._stub_json(schema, digest)
        return Completion(text=text, json_value=json_value, tokens_used=64, model="stub")

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
        all_providers = ["groq", "anthropic", "openai"]
        if primary in all_providers:
            all_providers.remove(primary)
        fallback_chain = [primary] + all_providers

        # Only try providers that have API keys configured
        s = get_settings()
        configured = []
        for p in fallback_chain:
            if p == "groq" and s.groq_api_key.strip():
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
        """Map a logical model to the correct model name for each provider."""
        s = get_settings()
        if provider == "groq":
            # The model from pick_model() is already a Groq model name — use it directly
            return model
        if provider == "openai":
            if "haiku" in model or "small" in model or "8b" in model or "instant" in model:
                return "gpt-4o-mini"
            return "gpt-4o"
        # anthropic — use as-is
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
            json_value = json.loads(content)
            self._validate_json(schema, json_value)
            tokens = resp.usage.total_tokens if resp.usage else 0
            return Completion(text=content, json_value=json_value, tokens_used=tokens, model=model)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": full_prompt}],
        )
        text = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return Completion(text=text, tokens_used=tokens, model=model)

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

        client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)
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
        return Completion(text=text, tokens_used=resp.usage.input_tokens + resp.usage.output_tokens, model=model)

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

        client = openai.OpenAI(api_key=get_settings().openai_api_key)
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
            json_value = json.loads(content)
            self._validate_json(schema, json_value)
            tokens = resp.usage.total_tokens if resp.usage else 0
            return Completion(text=content, json_value=json_value, tokens_used=tokens, model=model)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": full_prompt}],
        )
        text = resp.choices[0].message.content or ""
        tokens = resp.usage.total_tokens if resp.usage else 0
        return Completion(text=text, tokens_used=tokens, model=model)

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
