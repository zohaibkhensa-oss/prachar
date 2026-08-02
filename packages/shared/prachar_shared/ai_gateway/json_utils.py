"""Universal JSON extraction utility.

Handles all common LLM output formats:
- Plain JSON objects/arrays
- JSON wrapped in markdown code fences (```json ... ``` or ``` ... ```)
- JSON with leading/trailing prose
- JSON with trailing whitespace
- JSON with escaped unicode
- JSON with BOM or other invisible characters

Never raises on formatting — only on genuinely unparseable content.
"""
from __future__ import annotations

import json
import re
from typing import Any

# Regex to find ```json ... ``` or ``` ... ``` blocks
_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)

# Regex to find the first { or [ and last } or ] — for prose-wrapped JSON
_OBJECT_RE = re.compile(r"(\{.*\})", re.DOTALL)
_ARRAY_RE = re.compile(r"(\[.*\])", re.DOTALL)


def extract_json(text: str) -> dict[str, Any] | list[Any] | None:
    """Extract and parse JSON from an LLM response.

    Tries multiple strategies in order:
    1. Direct parse (plain JSON)
    2. Strip markdown code fences
    3. Extract first JSON object/array from surrounding prose
    4. Strip BOM and invisible characters

    Returns parsed JSON (dict or list) or None if no valid JSON found.
    Never raises — returns None on failure so callers can handle gracefully.
    """
    if not text or not text.strip():
        return None

    # Strip BOM and zero-width characters
    cleaned = text.replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "")

    # Strategy 1: Direct parse
    result = _try_parse(cleaned.strip())
    if result is not None:
        return result

    # Strategy 2: Extract from markdown code fences
    fence_match = _FENCE_RE.search(cleaned)
    if fence_match:
        fenced = fence_match.group(1).strip()
        result = _try_parse(fenced)
        if result is not None:
            return result

    # Strategy 3: Extract first JSON object from prose
    obj_match = _OBJECT_RE.search(cleaned)
    if obj_match:
        result = _try_parse(obj_match.group(1).strip())
        if result is not None:
            return result

    # Strategy 4: Extract first JSON array from prose
    arr_match = _ARRAY_RE.search(cleaned)
    if arr_match:
        result = _try_parse(arr_match.group(1).strip())
        if result is not None:
            return result

    # Strategy 5: Try removing common prefixes like "Here is..." / "Sure, ..."
    # Find first { or [ and try from there
    for i, ch in enumerate(cleaned):
        if ch in "{[":
            # Find matching close bracket
            close = "}" if ch == "{" else "]"
            # Search backwards from end for last close bracket
            for j in range(len(cleaned) - 1, i, -1):
                if cleaned[j] == close:
                    result = _try_parse(cleaned[i : j + 1])
                    if result is not None:
                        return result
                    break

    return None


def _try_parse(s: str) -> dict[str, Any] | list[Any] | None:
    """Try to parse a string as JSON. Returns None on failure."""
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None


def extract_json_or_raise(text: str, *, context: str = "") -> dict[str, Any] | list[Any]:
    """Extract JSON or raise a descriptive error.

    Use this when the caller wants strict JSON and prefers an exception
    over None (e.g., for retry logic).
    """
    result = extract_json(text)
    if result is None:
        preview = text[:200] if text else "(empty)"
        ctx = f" (context: {context})" if context else ""
        raise ValueError(f"Failed to extract JSON from LLM response{ctx}. Preview: {preview!r}")
    return result
