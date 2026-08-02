"""Fire 100 different user messages through the Orb and check for:
1. Internal/backend language leakage (engine, tool, DAG, council, etc.)
2. Faulty reasoning (empty responses, fallback messages, wrong intent)
3. User-facing copy quality

Usage: PYTHONPATH=apps/api:packages/shared:. .venv/bin/python test_orb_language.py
"""
import asyncio
import uuid
import logging
import sys
import json
from datetime import datetime

logging.basicConfig(level=logging.WARNING)

from prachar_shared.ai_gateway import AIGateway, Tier
from prachar_api.runtime.planner import IntentEngine, Planner, IntentResult, RuntimeMode
from prachar_api.runtime.context import (
    AIContext, BrandInfo, BillingInfo, MemoryStore, Permissions, UserPreferences,
)
from prachar_api.runtime import tools  # trigger tool registration

# ─── Banned words that should NEVER appear in user-facing copy ─────────────
BANNED_WORDS = [
    "engine", "engines", "pipeline", "dag", "node", "nodes", "graph",
    "tool", "tools", "module", "service", "api", "endpoint",
    "registry", "executor", "planner", "runtime", "framework",
    "council", "director", "directors", "campaignbrain", "creative_studio",
    "agency_council", "consensus_engine", "mi_engine",
]

# ─── 30 test messages across all categories ────────────────────────────────
# Reduced from 100 to 30 due to Groq free tier rate limit (6000 TPM).
# These 30 cover every category: campaign creation, analytics, creative,
# strategy, chat, edge cases, platform-specific, and billing.
MESSAGES = [
    # ── Campaign Creation (6) ──
    "Create a Diwali campaign for my brand",
    "I want to launch a new campaign for my restaurant",
    "Make a campaign for my SaaS startup with ₹50,000 budget",
    "Create a summer sale campaign for my online clothing store",
    "I need a campaign to get more app downloads",
    "Create a New Year campaign for my jewellery brand",

    # ── Performance & Analytics (5) ──
    "How is my campaign performing?",
    "What's my ROI?",
    "Which campaign is doing the best?",
    "What's my visibility score?",
    "How are my YouTube videos doing?",

    # ── Creative Requests (5) ──
    "Generate an image for my Diwali post",
    "Create a video for my product",
    "Write a caption for my Instagram post",
    "Make a poster for my sale",
    "Generate ad copy for my new product",

    # ── Strategy & Consultation (5) ──
    "What should my marketing strategy be?",
    "How can I improve my brand visibility?",
    "Who is my target audience?",
    "How should I allocate my marketing budget?",
    "What's the best marketing approach for a small budget?",

    # ── General Chat & Navigation (3) ──
    "Hello",
    "What can you do?",
    "What is PRACHAR?",

    # ── Edge Cases & Ambiguous (3) ──
    "I'm confused",
    "What should I do?",
    "I don't know where to start",

    # ── Platform-Specific (2) ──
    "Connect my Google Ads account",
    "My Facebook ads aren't running",

    # ── Budget & Billing (1) ──
    "How much should I spend on ads?",
]


async def test_single_message(
    intent_engine: IntentEngine,
    planner: Planner,
    ctx: AIContext,
    message: str,
    idx: int,
) -> dict:
    """Test a single message and return results."""
    result = {
        "idx": idx,
        "message": message,
        "intent": "",
        "mode": "",
        "confidence": 0.0,
        "user_explanation": "",
        "reasoning": "",
        "goal": "",
        "banned_in_explanation": [],
        "banned_in_reasoning": [],
        "issues": [],
        "status": "PASS",
    }

    # Step 1: Classify intent (with retry for rate limits)
    for attempt in range(4):
        try:
            intent = await intent_engine.classify(ctx, message)
            result["intent"] = intent.intent
            result["mode"] = intent.mode.value if intent.mode else ""
            result["confidence"] = intent.confidence
            break
        except Exception as e:
            if "429" in str(e) and attempt < 3:
                wait = 15 * (attempt + 1)
                print(f"       ⏳ Rate limited, waiting {wait}s... (attempt {attempt+1}/4)")
                await asyncio.sleep(wait)
            else:
                result["issues"].append(f"Intent classification failed: {e}")
                result["status"] = "FAIL"
                return result

    # Throttle between calls to respect Groq free tier (6000 TPM)
    await asyncio.sleep(3)

    # Step 2: Plan (with retry for rate limits)
    for attempt in range(4):
        try:
            plan = await planner.plan(ctx, message, intent)
            result["user_explanation"] = plan.user_explanation or ""
            result["reasoning"] = plan.reasoning or ""
            result["goal"] = plan.goal or ""
            break
        except Exception as e:
            if "429" in str(e) and attempt < 3:
                wait = 15 * (attempt + 1)
                print(f"       ⏳ Rate limited, waiting {wait}s... (attempt {attempt+1}/4)")
                await asyncio.sleep(wait)
            else:
                result["issues"].append(f"Planning failed: {e}")
                result["status"] = "FAIL"
                return result

    # Step 3: Check for banned words in user-facing copy
    explanation_lower = result["user_explanation"].lower()
    reasoning_lower = result["reasoning"].lower()

    for word in BANNED_WORDS:
        if word in explanation_lower:
            result["banned_in_explanation"].append(word)
        if word in reasoning_lower:
            result["banned_in_reasoning"].append(word)

    # Step 4: Check for quality issues
    if not result["user_explanation"].strip():
        result["issues"].append("Empty user_explanation")
        result["status"] = "FAIL"

    if result["user_explanation"] == "Let me think about that and get back to you.":
        result["issues"].append("Fallback message (planner failed)")
        result["status"] = "WARN"

    if result["confidence"] < 0.5 and intent.intent != "conversation":
        result["issues"].append(f"Low confidence: {result['confidence']}")
        result["status"] = "WARN"

    if result["banned_in_explanation"]:
        result["issues"].append(f"Banned words in user-facing copy: {result['banned_in_explanation']}")
        result["status"] = "FAIL"

    if result["banned_in_reasoning"]:
        result["issues"].append(f"Banned words in reasoning: {result['banned_in_reasoning']}")
        if result["status"] != "FAIL":
            result["status"] = "WARN"

    # Check for generic/empty responses
    generic_responses = [
        "Let me think about that and get back to you.",
        "Conversation mode — no tools needed except chat",
    ]
    if result["user_explanation"] in generic_responses and intent.intent != "conversation":
        result["issues"].append("Generic fallback for non-conversation intent")
        result["status"] = "WARN"

    return result


async def main():
    gw = AIGateway()
    intent_engine = IntentEngine(gw)
    planner = Planner(gw)

    ctx = AIContext(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        brand_id=uuid.uuid4(),
        brand=BrandInfo(
            name="Spice Route Restaurant",
            category="Restaurant",
            id="1",
            website="https://spiceroute.example.com",
            customer_type="b2c",
            locales=["en-IN"],
            tone="warm",
            visibility_score=42,
        ),
        billing=BillingInfo(plan="growth", ai_tokens_used=0, ai_budget=200000),
        memory=MemoryStore(),
        permissions=Permissions(role="owner"),
        user_preferences=UserPreferences(),
    )

    print("=" * 70)
    print("  ORB LANGUAGE & REASONING TEST — 30 MESSAGES")
    print("  (Groq free tier: 6000 TPM — throttled with retry)")
    print("=" * 70)
    print()
    print(f"Brand: Spice Route Restaurant (Restaurant, B2C, India)")
    print(f"Plan: Growth")
    print(f"LLM: Groq (llama-3.3-70b-versatile)")
    print(f"Banned words: {len(BANNED_WORDS)} terms")
    print(f"Test messages: {len(MESSAGES)}")
    print()
    print("-" * 70)
    print()

    results = []
    passed = 0
    warned = 0
    failed = 0
    t0 = datetime.now()

    for i, msg in enumerate(MESSAGES, 1):
        result = await test_single_message(intent_engine, planner, ctx, msg, i)
        results.append(result)

        # Throttle between messages to respect Groq free tier
        if i < len(MESSAGES):
            await asyncio.sleep(2)

        if result["status"] == "PASS":
            passed += 1
            symbol = "✅"
        elif result["status"] == "WARN":
            warned += 1
            symbol = "⚠️"
        else:
            failed += 1
            symbol = "❌"

        # Print compact line
        explanation_preview = result["user_explanation"][:60]
        if len(result["user_explanation"]) > 60:
            explanation_preview += "..."

        print(f"{symbol} [{i:3d}] intent={result['intent']:25s} conf={result['confidence']:.2f}")
        print(f"       msg: {msg[:55]}")
        print(f"       orb: {explanation_preview}")
        if result["issues"]:
            for issue in result["issues"]:
                print(f"       ⚠  {issue}")
        print()

    elapsed = (datetime.now() - t0).total_seconds()

    # ─── Summary ───────────────────────────────────────────────────────────
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print()
    print(f"  Total messages:    {len(MESSAGES)}")
    print(f"  Time:              {elapsed:.1f}s ({elapsed/len(MESSAGES):.1f}s per message)")
    print(f"  ✅ Passed:          {passed}")
    print(f"  ⚠️  Warnings:        {warned}")
    print(f"  ❌ Failed:          {failed}")
    print()

    # ─── Failed details ────────────────────────────────────────────────────
    if failed > 0:
        print("=" * 70)
        print("  FAILURES (banned words in user-facing copy)")
        print("=" * 70)
        print()
        for r in results:
            if r["status"] == "FAIL":
                print(f"  [{r['idx']}] \"{r['message']}\"")
                print(f"       Orb said: \"{r['user_explanation']}\"")
                for issue in r["issues"]:
                    print(f"       → {issue}")
                print()

    # ─── Warnings details ──────────────────────────────────────────────────
    if warned > 0:
        print("=" * 70)
        print("  WARNINGS (banned words in reasoning / low confidence / fallbacks)")
        print("=" * 70)
        print()
        for r in results:
            if r["status"] == "WARN":
                print(f"  [{r['idx']}] \"{r['message']}\"")
                for issue in r["issues"]:
                    print(f"       → {issue}")
                print()

    # ─── Intent distribution ───────────────────────────────────────────────
    print("=" * 70)
    print("  INTENT DISTRIBUTION")
    print("=" * 70)
    print()
    intent_counts: dict[str, int] = {}
    for r in results:
        intent_counts[r["intent"]] = intent_counts.get(r["intent"], 0) + 1
    for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
        bar = "█" * count
        print(f"  {intent:30s} {count:3d} {bar}")
    print()

    # ─── All banned words found ────────────────────────────────────────────
    all_banned: dict[str, int] = {}
    for r in results:
        for w in r["banned_in_explanation"] + r["banned_in_reasoning"]:
            all_banned[w] = all_banned.get(w, 0) + 1
    if all_banned:
        print("=" * 70)
        print("  BANNED WORDS FOUND (across all responses)")
        print("=" * 70)
        print()
        for word, count in sorted(all_banned.items(), key=lambda x: -x[1]):
            where = []
            for r in results:
                if word in r["banned_in_explanation"]:
                    where.append(f"#{r['idx']} (user-facing!)")
                if word in r["banned_in_reasoning"]:
                    where.append(f"#{r['idx']} (reasoning)")
            print(f"  \"{word}\": {count} times")
            for w in where[:5]:
                print(f"    - {w}")
            if len(where) > 5:
                print(f"    ... and {len(where) - 5} more")
            print()

    # ─── Final verdict ─────────────────────────────────────────────────────
    print("=" * 70)
    if failed == 0 and warned == 0:
        print("  ✅ ALL 100 MESSAGES CLEAN — No backend language leaked")
    elif failed == 0:
        print(f"  ✅ USER-FACING COPY CLEAN — {warned} warnings in internal reasoning")
    else:
        print(f"  ❌ {failed} FAILURES — Backend language leaked to user")
    print("=" * 70)

    # Save full results to file
    with open("/Users/appple/Projects/prachar/orb_test_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print()
    print("  Full results saved to: orb_test_results.json")

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
