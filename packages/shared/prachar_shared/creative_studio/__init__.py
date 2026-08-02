"""Creative Studio — spec registry for 10 creative formats.

A Creative Format Spec describes one of the 10 creative formats the Creative
Studio can generate from a single campaign (poster, video script, carousel,
story, whatsapp, facebook, linkedin, email, landing page, sms).

Each spec is a declarative dataclass — it contains NO generation logic. A
future generation layer reads the spec, fills the prompt_template, calls the
AI gateway, and validates the returned JSON against output_schema.

Usage:
    from prachar_shared.creative_studio import CreativeFormatRegistry

    reg = CreativeFormatRegistry()
    reg.get("poster")          # → CreativeFormatSpec(id="poster", ...)
    reg.all()                  # → list of all 10 specs
    reg.ids()                  # → ["poster", "video_script", ...]

The registry auto-registers all formats on first instantiation.
"""
from __future__ import annotations

from .base import (
    CreativeFormatRegistry,
    CreativeFormatSpec,
    get_registry,
    register_all,
)
from .studio import CreativePackage, CreativeStudio

# Auto-register all formats on import.
register_all()

__all__ = [
    "CreativeFormatSpec",
    "CreativeFormatRegistry",
    "CreativePackage",
    "CreativeStudio",
    "get_registry",
    "register_all",
]
