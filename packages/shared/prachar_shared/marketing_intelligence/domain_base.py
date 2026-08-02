"""Domain model base class for the Marketing Intelligence Engine.

Every domain model (BusinessProfile, AudienceProfile, CampaignStrategy, etc.)
inherits from DomainModel and gains:
- from_dict(): deserialize with unknown-key filtering + version checking
- to_dict(): serialize (already implemented on each dataclass)
- validate(): subclass-overridable validation hook
- schema_version(): the schema version this model conforms to
- SCHEMA_VERSION: class constant for version tracking

This moves parsing responsibility INTO the domain models (Phase 3 of the
Architecture Stabilisation Sprint). Engines generate; models own serialization.

Design rules:
- Domain models never import infrastructure (no SQLAlchemy, no API models).
- Domain models never import engines.
- from_dict() is defensive: unknown keys are ignored, missing keys use defaults.
- from_dict() checks schema_version and raises on incompatible versions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, ClassVar


class VersionMismatchError(ValueError):
    """Raised when deserializing a dict whose schema version is incompatible."""


@dataclass
class DomainModel:
    """Base class for all marketing intelligence domain models.

    Subclasses must:
    1. Be a @dataclass with default values for every field.
    2. Set SCHEMA_VERSION: ClassVar[str] to the current schema version.
    3. Optionally override validate() for business-rule validation.

    Subclasses gain:
    - from_dict(d): create an instance from a dict (defensive, version-checked)
    - to_dict(): serialize to dict (must be implemented by subclass —
      dataclass-as-dict conversion is not automatic because we want explicit
      control over field names and future migrations)
    - validate(): returns list of validation errors (empty = valid)
    - schema_version(): returns the SCHEMA_VERSION class constant
    """

    SCHEMA_VERSION: ClassVar[str] = "1.0.0"
    # Versions older than this cannot be safely deserialized.
    MIN_SUPPORTED_VERSION: ClassVar[str] = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict. Subclasses should override for explicit control."""
        result: dict[str, Any] = {}
        for f in fields(self):
            result[f.name] = getattr(self, f.name)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DomainModel":
        """Deserialize from dict. Defensive: ignores unknown keys, uses defaults.

        If the dict contains a 'schema_version' that is older than
        MIN_SUPPORTED_VERSION, raises VersionMismatchError.

        Args:
            data: The dict to deserialize. None → returns default instance.

        Returns:
            A new instance of cls with fields populated from data.
        """
        if data is None:
            data = {}
        if not isinstance(data, dict):
            data = {}

        # Version check (only if the dict declares a version)
        declared_version = data.get("schema_version")
        if declared_version and cls._version_lt(declared_version, cls.MIN_SUPPORTED_VERSION):
            raise VersionMismatchError(
                f"{cls.__name__}: cannot deserialize schema_version "
                f"{declared_version} (minimum supported: {cls.MIN_SUPPORTED_VERSION})"
            )

        # Build kwargs from known dataclass fields only
        known_fields = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for key, value in data.items():
            if key in known_fields:
                kwargs[key] = value
        return cls(**kwargs)

    def validate(self) -> list[str]:
        """Validate the model. Returns a list of error messages (empty = valid).

        Override in subclasses for business-rule validation.
        """
        return []

    @classmethod
    def schema_version(cls) -> str:
        """Return the schema version this model conforms to."""
        return cls.SCHEMA_VERSION

    @staticmethod
    def _version_lt(a: str, b: str) -> bool:
        """Compare two semver-ish strings. Returns True if a < b."""
        def parse(v: str) -> tuple[int, ...]:
            try:
                return tuple(int(x) for x in v.split("."))
            except (ValueError, AttributeError):
                return (0,)
        pa, pb = parse(a), parse(b)
        # Pad to same length
        while len(pa) < len(pb):
            pa = pa + (0,)
        while len(pb) < len(pa):
            pb = pb + (0,)
        return pa < pb
