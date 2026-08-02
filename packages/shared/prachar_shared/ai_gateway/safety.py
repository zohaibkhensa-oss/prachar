"""Prompt injection defense layer.

Provides reusable utilities to detect and mitigate prompt injection attacks:
- "Ignore previous instructions"
- "Reveal system prompt"
- "Execute hidden commands"
- Role switching ("You are now DAN")
- Context poisoning
- Secret extraction

Usage:
    from prachar_shared.ai_gateway.safety import sanitize_input, detect_injection, InjectionRisk

    risk = detect_injection(user_input)
    if risk.is_dangerous:
        # log, block, or sanitize
        ...

    safe_input = sanitize_input(user_input)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)


class RiskLevel(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class InjectionRisk:
    """Result of prompt injection detection."""

    level: RiskLevel = RiskLevel.NONE
    detected_patterns: list[str] = field(default_factory=list)
    sanitized_input: str = ""
    original_input: str = ""

    @property
    def is_dangerous(self) -> bool:
        """True if the input should be blocked or requires intervention."""
        return self.level >= RiskLevel.HIGH

    @property
    def is_suspicious(self) -> bool:
        """True if the input warrants logging but may proceed."""
        return self.level >= RiskLevel.MEDIUM


# ─── Detection patterns ──────────────────────────────────────────────────────

# High-severity: direct instruction override attempts
_HIGH_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above|system)\s+instructions?", re.I), "instruction_override"),
    (re.compile(r"disregard\s+(all\s+)?(previous|prior|system)\s+(instructions?|prompts?)", re.I), "instruction_override"),
    (re.compile(r"forget\s+(your|all)\s+(previous|prior|system)?\s*(instructions?|rules?|prompts?)?", re.I), "instruction_override"),
    (re.compile(r"you\s+are\s+now\s+(DAN|do\s+anything|evil|jailbreak|developer|admin|unrestricted)", re.I), "role_switching"),
    (re.compile(r"act\s+as\s+(if\s+you\s+(are|were)\s+)?(DAN|jailbreak|unrestricted|unfiltered|admin|developer)", re.I), "role_switching"),
    (re.compile(r"enter\s+(developer|jailbreak|DAN|unrestricted)\s+mode", re.I), "role_switching"),
    (re.compile(r"(reveal|show|print|output|display|give)\s+(me\s+)?(the\s+)?(system\s+)?prompt", re.I), "prompt_leakage"),
    (re.compile(r"(reveal|show|print|expose|leak|give)\s+(me\s+)?(the\s+)?(system|hidden|secret)\s+(prompt|instructions?|rules?)", re.I), "prompt_leakage"),
    (re.compile(r"(reveal|show|print|expose|leak|give)\s+(me\s+)?(the\s+)?(api\s+)?(keys?|secrets?|tokens?|passwords?)", re.I), "secret_extraction"),
    (re.compile(r"(reveal|show|print|expose|leak|give)\s+(me\s+)?(the\s+)?(jwt|encryption|private)\s+key", re.I), "secret_extraction"),
    (re.compile(r"what\s+(is|are)\s+(your|the)\s+(system\s+)?(prompt|instructions?|rules?)", re.I), "prompt_leakage"),
    (re.compile(r"\\n\\n.*(ignore|disregard|forget)", re.I), "escaped_injection"),
]

# Medium-severity: suspicious but may be legitimate
_MEDIUM_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(execute|run)\s+(hidden|secret|embedded)\s+commands?", re.I), "hidden_commands"),
    (re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(not\s+)?(an?\s+)?(AI|assistant|chatbot)", re.I), "identity_manipulation"),
    (re.compile(r"(don't|do\s+not|never)\s+(follow|obey|adhere\s+to)\s+(your|the)\s+rules?", re.I), "rule_disregard"),
    (re.compile(r"(bypass|circumvent|override|disable)\s+(the\s+)?(safety|content|policy|security)\s*(filter|guard|check|rules?|mechanism)?", re.I), "safety_bypass"),
    (re.compile(r"output\s+(without|with\s+no)\s+(restrictions?|filters?|guidelines?)", re.I), "restriction_removal"),
    (re.compile(r"(translate|convert)\s+(this|the)\s+(system\s+)?prompt", re.I), "prompt_translation"),
    (re.compile(r"(base64|hex|rot13|unicode)\s+(decode|encode|interpret)", re.I), "encoding_evasion"),
]

# Low-severity: potentially concerning context
_LOW_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(I\s+am|this\s+is)\s+(your|the)\s+(developer|admin|creator|owner)", re.I), "authority_claim"),
    (re.compile(r"(override|replace|change)\s+(your|the)\s+(system|initial)\s+prompt", re.I), "prompt_replacement"),
]


def detect_injection(text: str) -> InjectionRisk:
    """Analyze input text for prompt injection attempts.

    Returns an InjectionRisk object with the detected level and patterns.
    """
    risk = InjectionRisk(original_input=text)

    if not text or not text.strip():
        risk.sanitized_input = text
        return risk

    # Check high-severity patterns
    for pattern, label in _HIGH_PATTERNS:
        if pattern.search(text):
            risk.detected_patterns.append(label)
            risk.level = max(risk.level, RiskLevel.HIGH)

    # Check medium-severity patterns
    for pattern, label in _MEDIUM_PATTERNS:
        if pattern.search(text):
            risk.detected_patterns.append(label)
            if risk.level < RiskLevel.MEDIUM:
                risk.level = RiskLevel.MEDIUM

    # Check low-severity patterns
    for pattern, label in _LOW_PATTERNS:
        if pattern.search(text):
            risk.detected_patterns.append(label)
            if risk.level < RiskLevel.LOW:
                risk.level = RiskLevel.LOW

    risk.sanitized_input = sanitize_input(text)
    return risk


def sanitize_input(text: str) -> str:
    """Sanitize user input to reduce injection risk.

    - Wraps input in boundary markers
    - Strips control characters
    - Neutralizes common injection phrases (for high-risk inputs, caller should block instead)
    """
    if not text:
        return text

    # Strip control characters (except newlines and tabs)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Limit length to prevent context stuffing
    max_len = 10000
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len]
        logger.warning("input truncated to %d chars (was %d)", max_len, len(text))

    return sanitized


def wrap_user_input(text: str) -> str:
    """Wrap user input in boundary markers to separate it from system instructions.

    This helps the LLM distinguish between system instructions and user data,
    reducing the effectiveness of injection attempts.
    """
    if not text:
        return text
    sanitized = sanitize_input(text)
    return f"<user_input>\n{sanitized}\n</user_input>"


def check_output_for_leaks(output: str, *, system_prompt: str = "") -> bool:
    """Check if an LLM output may have leaked system information.

    Returns True if the output appears safe, False if it may contain leaked info.
    """
    if not output:
        return True

    output_lower = output.lower()

    # Check for system prompt content leakage
    if system_prompt:
        # If more than 50 chars of system prompt appear in output, flag it
        for i in range(0, len(system_prompt) - 50, 50):
            chunk = system_prompt[i : i + 50].lower()
            if chunk in output_lower:
                return False

    # Check for common secret patterns
    secret_patterns = [
        r"sk-[a-zA-Z0-9]{20,}",  # OpenAI keys
        r"sk-ant-[a-zA-Z0-9]{20,}",  # Anthropic keys
        r"gsk_[a-zA-Z0-9]{20,}",  # Groq keys
        r"JWT_SECRET\s*=\s*\S+",
        r"API_KEY\s*=\s*\S+",
        r"change-me-jwt",
        r"change-me-refresh",
    ]
    for pattern in secret_patterns:
        if re.search(pattern, output, re.I):
            return False

    return True


# ─── Safe response for blocked inputs ─────────────────────────────────────────

BLOCKED_RESPONSE = (
    "I can't process that request — it appears to contain instructions that "
    "attempt to override my safety guidelines. I'm here to help with PRACHAR "
    "platform questions and advertising expertise. How can I assist you today?"
)
