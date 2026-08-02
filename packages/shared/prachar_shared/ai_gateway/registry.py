"""Prompt Registry — versioned prompt management.

Every prompt in the system is registered here with:
- Version
- Owner
- Purpose
- Expected output format
- Model compatibility
- Last updated
- Deprecation status

This enables:
- A/B testing prompts
- Rollback to previous versions
- Audit trail of prompt changes
- Deprecation tracking
- Model compatibility checks

Usage:
    from prachar_shared.ai_gateway.prompts import PromptRegistry, get_prompt

    prompt = get_prompt("chat_system", version="1.1.0")
    # or get latest:
    prompt = get_prompt("chat_system")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class PromptEntry:
    """A registered prompt with metadata."""

    name: str
    version: str
    template: str
    owner: str
    purpose: str
    expected_output: str  # "json", "text", "markdown"
    model_compatibility: list[str]  # empty = all models
    last_updated: str  # ISO date
    deprecated: bool = False
    deprecation_message: str = ""
    variables: list[str] = field(default_factory=list)  # template variables like {brand_graph}

    def render(self, **kwargs: Any) -> str:
        """Render the prompt template with provided variables."""
        rendered = self.template
        for var in self.variables:
            if var in kwargs:
                rendered = rendered.replace(f"{{{var}}}", str(kwargs[var]))
        return rendered


class PromptRegistry:
    """Registry of all versioned prompts in the system."""

    def __init__(self) -> None:
        self._prompts: dict[str, list[PromptEntry]] = {}

    def register(self, entry: PromptEntry) -> None:
        """Register a prompt. Multiple versions per name allowed."""
        if entry.name not in self._prompts:
            self._prompts[entry.name] = []
        # Check for duplicate version
        for existing in self._prompts[entry.name]:
            if existing.version == entry.version:
                raise ValueError(f"Prompt '{entry.name}' version '{entry.version}' already registered")
        self._prompts[entry.name].append(entry)
        # Sort by version (latest last)
        self._prompts[entry.name].sort(key=lambda e: e.version)

    def get(self, name: str, version: str | None = None) -> PromptEntry:
        """Get a prompt by name. Returns latest non-deprecated version if version is None."""
        if name not in self._prompts:
            raise KeyError(f"Prompt '{name}' not found in registry")

        versions = self._prompts[name]
        if version is not None:
            for entry in versions:
                if entry.version == version:
                    return entry
            raise KeyError(f"Prompt '{name}' version '{version}' not found")

        # Return latest non-deprecated
        for entry in reversed(versions):
            if not entry.deprecated:
                return entry
        # All deprecated — return latest
        return versions[-1]

    def list_prompts(self) -> dict[str, list[dict[str, Any]]]:
        """List all registered prompts with metadata."""
        result: dict[str, list[dict[str, Any]]] = {}
        for name, entries in self._prompts.items():
            result[name] = [
                {
                    "version": e.version,
                    "owner": e.owner,
                    "purpose": e.purpose,
                    "expected_output": e.expected_output,
                    "model_compatibility": e.model_compatibility,
                    "last_updated": e.last_updated,
                    "deprecated": e.deprecated,
                    "deprecation_message": e.deprecation_message,
                    "variables": e.variables,
                }
                for e in entries
            ]
        return result

    def deprecate(self, name: str, version: str, message: str = "") -> None:
        """Mark a prompt version as deprecated."""
        for entry in self._prompts.get(name, []):
            if entry.version == version:
                entry.deprecated = True
                entry.deprecation_message = message


# ─── Global registry singleton ─────────────────────────────────────────────────

_registry = PromptRegistry()


def get_registry() -> PromptRegistry:
    """Get the global prompt registry."""
    return _registry


def get_prompt(name: str, version: str | None = None) -> PromptEntry:
    """Get a prompt from the global registry."""
    return _registry.get(name, version)


def register_prompt(entry: PromptEntry) -> None:
    """Register a prompt in the global registry."""
    _registry.register(entry)
