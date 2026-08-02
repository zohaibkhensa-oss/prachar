"""Creative Studio — base contracts and registry.

A Creative Format Spec describes one of the 10 creative formats the Creative
Studio can generate from a single campaign (poster, video script, carousel,
story, whatsapp, facebook, linkedin, email, landing page, sms).

Each spec is a small immutable dataclass that defines:
  - id, label, description
  - output_schema (dict describing the JSON the AI should return)
  - prompt_template (string with {campaign}, {creative_direction},
    {domain_context} placeholders)
  - max_tokens, tier (free/pro/enterprise)

Adding a new format:
  1. Create a file under creative_studio/formats/<format>.py
  2. Define a `CreativeFormatSpec(...)` constant
  3. Register it in creative_studio/formats/__init__.py

Zero core modifications. No router changes, no UI changes. The generation
logic lives in a separate layer (future parts).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CreativeFormatSpec:
    """A spec describing one creative format the studio can produce.

    The spec is intentionally declarative — it contains NO generation logic.
    A future generation layer reads the spec, fills the prompt_template with
    {campaign}, {creative_direction}, {domain_context}, calls the AI gateway,
    and validates the returned JSON against output_schema.
    """

    id: str                          # "poster", "video_script", ...
    label: str                       # "Poster", "Video Script"
    description: str                 # short human description
    output_schema: dict[str, Any]    # JSON schema describing the AI output
    prompt_template: str             # prompt with {campaign}, {creative_direction}, {domain_context}
    max_tokens: int = 2000
    tier: str = "free"               # "free" | "pro" | "enterprise"


# ─── Registry ──────────────────────────────────────────────────────────────


class CreativeFormatRegistry:
    """Registry of available creative format specs. Singleton.

    Instantiating ``CreativeFormatRegistry()`` always returns the same shared
    instance (via ``__new__``), so callers can use either ``CreativeFormatRegistry()``
    or ``CreativeFormatRegistry.instance()`` interchangeably. This mirrors the
    DomainPackRegistry pattern while also ensuring a bare constructor sees all
    auto-registered formats.
    """

    _instance: "CreativeFormatRegistry | None" = None

    def __new__(cls) -> "CreativeFormatRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._specs = {}  # type: ignore[attr-defined]
        return cls._instance

    def __init__(self) -> None:
        # State is initialised in __new__; avoid resetting on repeated calls.
        if not hasattr(self, "_specs"):
            self._specs: dict[str, CreativeFormatSpec] = {}

    @classmethod
    def instance(cls) -> "CreativeFormatRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, spec: CreativeFormatSpec) -> None:
        if not spec.id:
            raise ValueError("CreativeFormatSpec.id is required")
        self._specs[spec.id] = spec

    def get(self, spec_id: str) -> CreativeFormatSpec | None:
        return self._specs.get(spec_id)

    def get_required(self, spec_id: str) -> CreativeFormatSpec:
        spec = self._specs.get(spec_id)
        if spec is None:
            raise KeyError(
                f"Unknown creative format: {spec_id!r}. "
                f"Available: {list(self._specs)}"
            )
        return spec

    def all(self) -> list[CreativeFormatSpec]:
        return list(self._specs.values())

    def ids(self) -> list[str]:
        return list(self._specs.keys())

    def clear(self) -> None:
        """Clear all registered specs (for tests)."""
        self._specs.clear()


def get_registry() -> CreativeFormatRegistry:
    """Get the singleton registry."""
    return CreativeFormatRegistry.instance()


def register_all() -> None:
    """Register all built-in creative format specs. Called at import time."""
    from .formats import ALL_FORMATS

    reg = get_registry()
    reg.clear()
    for spec in ALL_FORMATS:
        reg.register(spec)
