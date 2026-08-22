"""Intent Engine + Planner — classifies user message and builds execution graph.

Constitution Rule 7: The Planner reasons from manifests. Never hard-code intent→tool mappings.

Flow:
    message → Intent Engine → { intent, mode, confidence }
           → Planner → ExecutionPlan (graph + decision contract fields)
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from prachar_shared.ai_gateway import AIGateway, Tier, extract_json_or_raise

from .context import AIContext
from .graph import ExecutionGraph, GraphNode
from .registry import ToolManifest, ToolRegistry, get_registry

log = logging.getLogger("prachar.runtime.planner")


# ─── Runtime Modes (Amendment 7) ────────────────────────────────────────────


class RuntimeMode(str, Enum):
    """The Planner changes behaviour based on mode."""

    CONVERSATION = "conversation"   # quick chat, no tools except chat.respond
    RESEARCH = "research"           # read-only analysis, no writes
    PLANNING = "planning"           # create plans but don't execute (dry_run)
    CREATION = "creation"           # full execution, may require approval
    REVIEW = "review"               # council review mode
    EXECUTION = "execution"         # publishing, budget changes, always approval
    AUTOMATION = "automation"       # worker-triggered, no user input
    LEARNING = "learning"           # post-campaign learning


# ─── Intent Result ──────────────────────────────────────────────────────────


@dataclass
class IntentResult:
    """Output of the Intent Engine.

    Confidence thresholds (Step 1):
    - > 0.85: execute immediately
    - 0.60–0.85: ask a clarifying question
    - < 0.60: stay conversational, gather more context
    """

    intent: str = "conversation"      # "campaign.create", "performance.query", etc.
    mode: RuntimeMode = RuntimeMode.CONVERSATION
    confidence: float = 0.0
    reasoning: str = ""
    alternatives: list[str] = field(default_factory=list)  # "campaign.review", "creative.generate"
    clarifying_question: str = ""  # generated when confidence is mid

    # Confidence thresholds
    EXECUTE_THRESHOLD: float = 0.85
    CLARIFY_THRESHOLD: float = 0.60

    @property
    def should_execute(self) -> bool:
        """Confidence is high enough to execute without asking."""
        return self.confidence >= self.EXECUTE_THRESHOLD

    @property
    def should_clarify(self) -> bool:
        """Confidence is mid — ask a clarifying question before executing."""
        return self.CLARIFY_THRESHOLD <= self.confidence < self.EXECUTE_THRESHOLD

    @property
    def should_stay_conversational(self) -> bool:
        """Confidence is low — don't execute any workflow, just chat."""
        return self.confidence < self.CLARIFY_THRESHOLD

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "mode": self.mode.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "alternatives": self.alternatives,
            "clarifying_question": self.clarifying_question,
            "should_execute": self.should_execute,
            "should_clarify": self.should_clarify,
            "should_stay_conversational": self.should_stay_conversational,
        }


# ─── Execution Plan ─────────────────────────────────────────────────────────


@dataclass
class ExecutionPlan:
    """Output of the Planner — everything needed to create a Decision Contract."""

    goal: str = ""
    reasoning: str = ""
    intent: str = ""
    mode: RuntimeMode = RuntimeMode.CONVERSATION
    tools: list[str] = field(default_factory=list)
    graph: ExecutionGraph = field(default_factory=ExecutionGraph)
    risk_level: str = "low"
    requires_approval: bool = False
    approval_reason: str | None = None
    estimated_duration: str = "—"
    estimated_cost_usd: float = 0.0
    expected_outputs: list[str] = field(default_factory=list)
    user_explanation: str = ""  # Step 2: natural-language explanation for the user
    health_warnings: list[str] = field(default_factory=list)  # Phase E1.2: degraded/offline notices
    cost_breakdown: list[dict] = field(default_factory=list)  # Phase E2.2: per-tool {tool, cost, latency, quality}


# ─── Intent Engine ──────────────────────────────────────────────────────────


INTENT_PROMPT = """\
You are CURV AI. Classify the user's message into an intent and mode.

Available intents (choose the closest match):
- conversation: general chat, questions, greetings
- campaign.create: user wants to create/launch a new marketing campaign (strategy, budget, channels)
- campaign.review: user wants to review/critique an existing campaign
- performance.query: user asks about results, metrics, how things are doing
- creative.image: user wants to generate an image, photo, poster, visual, or artwork
- creative.video: user wants to generate a video, clip, reel, or short film
- creative.repurpose: user wants to repurpose content
- proactive.query: user asks what needs attention, what's wrong
- onboarding.consult: user is describing their business for the first time
- youtube.plan: user wants a YouTube video plan (strategy, not actual video generation)
- memory.query: user asks what the AI knows/remembers
- channel.publish: user wants to publish or post content to a social media channel

IMPORTANT disambiguation:
- "create a video" / "make a video" / "generate a video" → creative.video (NOT campaign.create)
- "create an image" / "make a poster" / "generate a photo" → creative.image (NOT campaign.create)
- "create a campaign" / "launch a campaign" / "build a campaign" → campaign.create
- "publish to YouTube" / "post to Instagram" → channel.publish
- "create a YouTube plan" / "plan a YouTube video" → youtube.plan (strategy, not generation)

Available modes:
- conversation: quick chat
- research: read-only analysis
- planning: create a plan but don't execute
- creation: full execution
- review: council review
- execution: publish/approve actions
- learning: post-campaign learning

Confidence scoring:
- 0.90+: User's message is unambiguous. Intent is clear.
- 0.70–0.89: Intent is likely correct but could be interpreted differently.
- 0.50–0.69: Message is vague. Multiple intents could apply.
- Below 0.50: Message is too vague to determine intent.

Always provide 1-2 alternative intents (in descending likelihood) and a \
clarifying question that would help disambiguate if confidence is below 0.85.

Respond as JSON:
{{
  "intent": "campaign.create",
  "mode": "creation",
  "confidence": 0.92,
  "reasoning": "User explicitly asked to create a campaign with a budget",
  "alternatives": ["campaign.review", "creative.generate"],
  "clarifying_question": ""
}}

If confidence < 0.85, provide a clarifying question like:
"clarifying_question": "Do you want me to create a new campaign, or review an existing one?"

User message: {message}
Brand context: {brand_context}

CRITICAL: Your ENTIRE response must be a single valid JSON object. \
Do NOT include any markdown, headings, or text before or after the JSON. \
Start with {{ and end with }}. Nothing else.
"""


class IntentEngine:
    """Classifies user message → intent + mode."""

    def __init__(self, gateway: AIGateway) -> None:
        self._gateway = gateway

    def _fast_classify(self, message: str) -> IntentResult | None:
        """Fast regex-based pre-classifier for obvious creative intents.
        
        Catches clear cases (generate image/video) without needing an LLM call,
        avoiding rate limits and misclassification by weaker models.
        """
        msg = message.lower().strip()
        
        # Creative video — generate/make/create a video or advertisement
        video_patterns = [
            r"\b(generate|make|create|produce)\b.*\b(video|clip|reel|short film|movie|advertisement|launch ad|cinematic ad)\b",
            r"\b(video|clip|reel)\b.*\b(generate|make|create|produce)\b",
            r"\b\d+\s*[-]?\s*(second|sec|s)\b.*\b(video|clip|advertisement|ad)\b",
            r"\b(cinematic|launch)\b.*\b(advertisement|ad|video|clip)\b",
        ]
        for pattern in video_patterns:
            import re
            if re.search(pattern, msg):
                return IntentResult(
                    intent="creative.video",
                    mode=RuntimeMode.CREATION,
                    confidence=0.95,
                    reasoning="Fast classifier: user wants to generate a video",
                )
        
        # Creative image — generate/make/create an image/poster/photo
        image_patterns = [
            r"\b(generate|make|create|design|draw)\b.*\b(image|poster|photo|picture|visual|artwork|illustration|graphic)\b",
            r"\b(image|poster|photo|picture|visual|artwork)\b.*\b(generate|make|create|design)\b",
        ]
        for pattern in image_patterns:
            import re
            if re.search(pattern, msg):
                return IntentResult(
                    intent="creative.image",
                    mode=RuntimeMode.CREATION,
                    confidence=0.95,
                    reasoning="Fast classifier: user wants to generate an image",
                )
        
        # Channel publish — publish/post to a channel
        publish_patterns = [
            r"\b(publish|post|upload|share)\b.*\b(youtube|instagram|facebook|tiktok|linkedin|whatsapp|twitter|x)\b",
            r"\b(youtube|instagram|facebook|tiktok|linkedin)\b.*\b(publish|post|upload)\b",
        ]
        for pattern in publish_patterns:
            import re
            if re.search(pattern, msg):
                return IntentResult(
                    intent="channel.publish",
                    mode=RuntimeMode.EXECUTION,
                    confidence=0.95,
                    reasoning="Fast classifier: user wants to publish to a channel",
                )

        # Conversation — questions, advice, general chat (NOT campaign creation)
        # These are questions asking for information/advice, not requesting action
        conversation_patterns = [
            r"\b(what|how|why|when|where|which|can|could|should|would|do|does|is|are|will)\b.*\b(i|my|me|we|our|business|brand|restaurant|cafe|shop|store|company)\b",
            r"\b(what|how)\b.*\b(do|can|should|to)\b.*\b(promote|market|advertise|grow|improve|increase|boost|get more|reach)\b",
            r"\b(tell me about|explain|what is|what are|how does|how do)\b",
            r"\b(advice|tips|ideas|suggestions|recommendations)\b.*\b(for|on|about)\b",
            r"\b(hi|hello|hey|good morning|good evening|good afternoon)\b",
            r"\b(help|assist|support)\b.*\b(me|us|with)\b",
        ]
        for pattern in conversation_patterns:
            import re
            if re.search(pattern, msg):
                return IntentResult(
                    intent="conversation",
                    mode=RuntimeMode.CONVERSATION,
                    confidence=0.85,
                    reasoning="Fast classifier: user is asking a question or seeking advice (conversational)",
                )

        return None

    async def classify(self, ctx: AIContext, message: str) -> IntentResult:
        # Fast path: regex pre-classifier for obvious creative intents
        fast_result = self._fast_classify(message)
        if fast_result:
            log.info("fast classifier matched: %s (confidence=%.2f)", fast_result.intent, fast_result.confidence)
            return fast_result

        brand_ctx = ""
        if ctx.brand:
            brand_ctx = f"{ctx.brand.name} ({ctx.brand.category or 'unknown industry'})"

        prompt = INTENT_PROMPT.format(message=message, brand_context=brand_ctx)

        # Retry on rate limit errors
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                completion = await self._gateway.async_complete(
                    prompt=prompt,
                    tier=Tier.small,
                    task="intent_classification",
                    tenant_id=str(ctx.tenant_id),
                    plan=ctx.billing.plan,
                    max_tokens=200,
                    temperature=0.1,
                    model_override="allam-2-7b",
                )

                data = extract_json_or_raise(completion.text)
                # LLM may return a list — take first element
                if isinstance(data, list):
                    data = data[0] if data else {}
                if not isinstance(data, dict):
                    data = {}
                mode_str = data.get("mode", "conversation")
                try:
                    mode = RuntimeMode(mode_str)
                except ValueError:
                    mode = RuntimeMode.CONVERSATION

                return IntentResult(
                    intent=data.get("intent", "conversation"),
                    mode=mode,
                    confidence=float(data.get("confidence", 0.0)),
                    reasoning=data.get("reasoning", ""),
                    alternatives=data.get("alternatives", []),
                    clarifying_question=data.get("clarifying_question", ""),
                )
            except Exception as exc:
                last_exc = exc
                if "429" in str(exc) and attempt < 2:
                    wait = 15 * (attempt + 1)
                    log.warning("intent rate limited, retrying in %ds...", wait)
                    await asyncio.sleep(wait)
                else:
                    log.warning("intent classification failed: %s — defaulting to conversation", exc)
                    return IntentResult(
                        intent="conversation",
                        mode=RuntimeMode.CONVERSATION,
                        confidence=0.0,
                        reasoning="fallback: classification failed",
                    )
        log.warning("intent exhausted retries: %s — defaulting to conversation", last_exc)
        return IntentResult(
            intent="conversation",
            mode=RuntimeMode.CONVERSATION,
            confidence=0.0,
            reasoning="fallback: classification failed",
        )


# ─── Planner ────────────────────────────────────────────────────────────────


PLANNER_PROMPT = """\
You are the CURV AI Planner. Given a user's intent, brand context, and \
available tools, produce an execution plan as a directed acyclic graph (DAG) \
of tool calls.

Available tools:
{tools}

User intent: {intent}
Mode: {mode}
User message: {message}
Brand: {brand_name} ({brand_category})
Memory: {memory_summary}

Build an execution graph. Rules:
1. Tools that don't depend on each other should run in parallel (same parallel_group).
2. Tools that need outputs from other tools must list those in deps.
3. Tools with side effects (publish, approve) should have needs_approval=true.
4. In "planning" mode, don't include execution tools — only analysis + strategy.
5. In "conversation" mode, only use chat.respond.
6. In "research" mode, only use read-only tools (performance.*, proactive.*, memory.retrieve).
7. Always end with memory.update if the plan produces learnings.
8. user_explanation must be a natural, concise sentence (max 30 words) that \
explains the approach to the user in plain English. \
NEVER mention internal tool names, "engines", "directors", "council", \
"nodes", "graphs", "pipelines", "DAG", or any backend terminology. \
Speak as a helpful marketing partner would. \
Example: "I'll analyse your business, craft a creative strategy, and prepare \
your campaign. I'll show you everything for approval before publishing."
9. reasoning must also avoid backend jargon. Describe WHAT you're doing for \
the user, not HOW the system works internally. Never use the words "engine", \
"engines", "council", "directors", "tool", "tools", "pipeline", "DAG", \
"node", "nodes", "graph", "module", "service", "API", "endpoint". \
Instead of "council", say "my team". Instead of "engine", say "analysis" \
or "strategy" or the actual work being done.
10. When multiple tools can achieve the same goal, prefer the one with the best \
cost-efficiency (quality / cost). If speed is critical (user asked for 'quick' \
or 'fast'), prefer lower latency. If quality is critical (user asked for 'best' \
or 'premium'), prefer higher quality_score.

Respond as JSON:
{{
  "goal": "Create Diwali Campaign",
  "reasoning": "User wants a Diwali campaign. I'll understand their business, craft a strategy, create the creative concepts, plan the media spend, have my team review it, and prepare everything for their approval.",
  "user_explanation": "I'll analyse your business, craft a creative strategy, and prepare your Diwali campaign. I'll show you everything for approval before publishing.",
  "risk_level": "low",
  "requires_approval": false,
  "approval_reason": null,
  "estimated_duration": "45 seconds",
  "estimated_cost_usd": 0.15,
  "expected_outputs": ["Campaign", "Strategy", "Creative Direction", "Budget"],
  "graph": {{
    "nodes": [
      {{
        "id": "n1",
        "tool": "campaign_brain.analyse",
        "input": {{"goal": "...", "budget": "..."}},
        "deps": [],
        "parallel_group": null,
        "needs_approval": false
      }},
      {{
        "id": "n2",
        "tool": "campaign_brain.strategy",
        "input": {{"business_profile": "${{n1.result.business_profile}}"}},
        "deps": ["n1"],
        "parallel_group": null,
        "needs_approval": false
      }}
    ]
  }}
}}

Input references: Use ${{nodeId.result.fieldName}} to reference outputs from previous nodes.

CRITICAL: Your ENTIRE response must be a single valid JSON object. \
Do NOT include any markdown, headings, explanations, or text before or after \
the JSON. Do NOT wrap it in ```json``` code fences. \
Start your response with {{ and end it with }}. Nothing else.
"""


class Planner:
    """Builds an Execution Graph from an intent + context.

    The Planner reasons about Tool Manifests — it does NOT hard-code mappings.
    """

    def __init__(self, gateway: AIGateway, registry: ToolRegistry | None = None) -> None:
        self._gateway = gateway
        self._registry = registry or get_registry()

    async def plan(self, ctx: AIContext, message: str, intent: IntentResult) -> ExecutionPlan:
        # For conversation mode, short-circuit — just chat.respond
        if intent.mode == RuntimeMode.CONVERSATION:
            return self._conversation_plan(intent)

        # Fast path: for creative intents, use a hardcoded plan (avoids LLM
        # planner failures when the small model can't generate complex JSON)
        if intent.intent == "creative.video":
            return self._creative_video_plan(intent, message)
        if intent.intent == "creative.image":
            return self._creative_image_plan(intent, message)

        # Phase E1.2: Exclude offline and degraded tools from the prompt so
        # the Planner LLM only sees healthy capabilities.
        # Filter tools by intent to keep prompt small (avoids TPM rate limits)
        tools_for_prompt = self._filter_tools_by_intent(
            self._registry.list_for_prompt(only_healthy=True),
            intent.intent,
        )
        if intent.mode == RuntimeMode.RESEARCH:
            tools_for_prompt = self._filter_readonly_tools(tools_for_prompt)

        memory_summary = self._memory_summary(ctx)
        brand_name = ctx.brand.name if ctx.brand else "Unknown"
        brand_category = ctx.brand.category if ctx.brand else "unknown"

        # Build enriched context summary for the planner
        enriched_summary = self._enriched_summary(ctx)

        # Ranked prompt context (from Context Ranking Layer — scored, token-budgeted)
        ranked_context = ctx.prompt_context or ""

        prompt = PLANNER_PROMPT.format(
            tools=tools_for_prompt,
            intent=intent.intent,
            mode=intent.mode.value,
            message=message,
            brand_name=brand_name,
            brand_category=brand_category,
            memory_summary=memory_summary + enriched_summary + ranked_context,
        )

        # Retry on rate limit errors (Groq free tier: 6000 TPM)
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                completion = await self._gateway.async_complete(
                    prompt=prompt,
                    tier=Tier.small,
                    task="planner",
                    tenant_id=str(ctx.tenant_id),
                    plan=ctx.billing.plan,
                    max_tokens=2000,
                    temperature=0.2,
                )

                data = extract_json_or_raise(completion.text)
                # LLM may return a list instead of a dict — take first element
                if isinstance(data, list):
                    data = data[0] if data else {}
                if not isinstance(data, dict):
                    log.warning("planner returned unexpected type %s — falling back to conversation", type(data).__name__)
                    return self._conversation_plan(intent)
                return self._parse_plan(data, intent)
            except Exception as exc:
                last_exc = exc
                if "429" in str(exc) and attempt < 2:
                    wait = 15 * (attempt + 1)
                    log.warning("planner rate limited, retrying in %ds...", wait)
                    await asyncio.sleep(wait)
                else:
                    log.warning("planner failed: %s — falling back to conversation", exc)
                    return self._conversation_plan(intent)
        log.warning("planner exhausted retries: %s — falling back to conversation", last_exc)
        return self._conversation_plan(intent)

    def _conversation_plan(self, intent: IntentResult) -> ExecutionPlan:
        """Fallback: just chat.respond."""
        graph = ExecutionGraph()
        graph.add_node(GraphNode(
            tool="chat.respond",
            input={},
            deps=[],
        ))
        return ExecutionPlan(
            goal="Respond conversationally",
            reasoning="Conversation mode — respond directly to the user",
            intent=intent.intent,
            mode=intent.mode,
            tools=["chat.respond"],
            graph=graph,
            risk_level="low",
            requires_approval=False,
            estimated_duration="3 seconds",
            estimated_cost_usd=0.01,
            expected_outputs=["Reply"],
            user_explanation="Let me help you with that.",
            cost_breakdown=[{"tool": "chat.respond", "cost": 0.01, "latency": 2000, "quality": 0.7}],
        )

    def _creative_video_plan(self, intent: IntentResult, message: str = "") -> ExecutionPlan:
        """Fast path: generate a video using video_gen.generate."""
        # Parse duration from message (e.g. "30 second", "30-second", "5 sec", "10s")
        import re
        duration = 10  # default
        m = re.search(r'(\d+)\s*[-]?\s*(?:second|sec|s)\b', message.lower())
        if m:
            duration = int(m.group(1))
            duration = max(5, min(60, duration))

        graph = ExecutionGraph()
        graph.add_node(GraphNode(
            tool="video_gen.generate",
            input={"prompt": message, "duration": duration},
            deps=[],
        ))
        return ExecutionPlan(
            goal="Generate a cinematic video",
            reasoning="User wants to create a video — using video generation tool",
            intent=intent.intent,
            mode=intent.mode,
            tools=["video_gen.generate"],
            graph=graph,
            risk_level="low",
            requires_approval=False,
            estimated_duration="2-5 minutes",
            estimated_cost_usd=0.50,
            expected_outputs=["Video artefact"],
            user_explanation="I'll generate a cinematic video for you. This may take a few minutes.",
            cost_breakdown=[{"tool": "video_gen.generate", "cost": 0.50, "latency": 180000, "quality": 0.9}],
        )

    def _creative_image_plan(self, intent: IntentResult, message: str = "") -> ExecutionPlan:
        """Fast path: generate an image using image_gen.generate."""
        graph = ExecutionGraph()
        graph.add_node(GraphNode(
            tool="image_gen.generate",
            input={"prompt": message},
            deps=[],
        ))
        return ExecutionPlan(
            goal="Generate a creative image",
            reasoning="User wants to create an image — using image generation tool",
            intent=intent.intent,
            mode=intent.mode,
            tools=["image_gen.generate"],
            graph=graph,
            risk_level="low",
            requires_approval=False,
            estimated_duration="30-60 seconds",
            estimated_cost_usd=0.10,
            expected_outputs=["Image artefact"],
            user_explanation="I'll generate a creative image for you.",
            cost_breakdown=[{"tool": "image_gen.generate", "cost": 0.10, "latency": 45000, "quality": 0.9}],
        )

    def _parse_plan(self, data: dict[str, Any], intent: IntentResult) -> ExecutionPlan:
        """Parse the Planner LLM output into an ExecutionPlan."""
        from .health import HealthStatus, get_health_registry

        graph_data = data.get("graph", {})
        graph = ExecutionGraph.from_dict(graph_data)

        tools = [n.tool for n in graph.nodes]
        cost = float(data.get("estimated_cost_usd", 0.0))

        # Sum manifest costs for validation
        manifest_cost = 0.0
        cost_breakdown: list[dict] = []
        for node in graph.nodes:
            manifest = self._registry.get(node.tool)
            if manifest:
                manifest_cost += manifest.manifest.estimated_cost_usd
                cost_breakdown.append({
                    "tool": node.tool,
                    "cost": manifest.manifest.estimated_cost_usd,
                    "latency": manifest.manifest.estimated_latency_ms,
                    "quality": manifest.manifest.quality_score,
                })

        # Phase E1.2: Collect health warnings for degraded/offline tools in the plan
        health = get_health_registry()
        health_warnings: list[str] = []
        for tool_name in tools:
            h = health.get(tool_name)
            if h.status == HealthStatus.OFFLINE:
                health_warnings.append(
                    f"Tool '{tool_name}' is offline and will be skipped during execution."
                )
            elif h.status == HealthStatus.DEGRADED:
                health_warnings.append(
                    f"Tool '{tool_name}' is degraded — performance may be affected."
                )

        reasoning = data.get("reasoning", "")
        if health_warnings:
            reasoning = reasoning + "\n\nHealth notes:\n" + "\n".join(health_warnings)

        return ExecutionPlan(
            goal=data.get("goal", ""),
            reasoning=reasoning,
            intent=intent.intent,
            mode=intent.mode,
            tools=tools,
            graph=graph,
            risk_level=data.get("risk_level", "low"),
            requires_approval=bool(data.get("requires_approval", False)),
            approval_reason=data.get("approval_reason"),
            estimated_duration=data.get("estimated_duration", "—"),
            estimated_cost_usd=cost or manifest_cost,
            expected_outputs=data.get("expected_outputs", []),
            user_explanation=data.get("user_explanation", ""),
            health_warnings=health_warnings,
            cost_breakdown=cost_breakdown,
        )

    def _filter_readonly_tools(self, tools_text: str) -> str:
        """Filter tool list to read-only tools for research mode."""
        lines = tools_text.strip().split("\n")
        readonly = [
            line for line in lines
            if any(ro in line for ro in ["performance.", "proactive.", "memory.retrieve", "analytics."])
        ]
        return "\n".join(readonly) if readonly else tools_text

    def _filter_tools_by_intent(self, tools_text: str, intent: str) -> str:
        """Filter tool list to only tools relevant to the intent.
        
        This reduces the planner prompt size from ~19K chars to ~3K,
        avoiding Groq TPM rate limits while keeping planning quality.
        """
        # Always include chat.respond and memory.update
        always_include = ["chat.respond", "memory.update"]
        
        # Map intents to relevant tool prefixes
        intent_tools: dict[str, list[str]] = {
            "campaign.create": ["campaign_brain.", "council.review", "creative_studio.", "review.publish", "calendar."],
            "campaign.review": ["council.review", "review.list", "review.publish", "performance."],
            "performance.query": ["performance.", "attribution.", "channel.metrics", "ads.stats"],
            "creative.image": ["creative_studio.generate_image", "creative_studio."],
            "creative.video": ["video_gen.", "creator.youtube_plan", "creative_studio."],
            "creative.repurpose": ["creator.repurpose", "creative_studio."],
            "proactive.query": ["proactive.", "performance.", "review.list"],
            "onboarding.consult": ["consult.understand", "campaign_brain.analyse"],
            "youtube.plan": ["creator.youtube_plan", "creative_studio."],
            "memory.query": ["memory.retrieve", "memory.update"],
            "channel.publish": ["channel.publish", "channel.list", "channel.connect"],
        }
        
        relevant_prefixes = intent_tools.get(intent, [])
        if not relevant_prefixes:
            # Unknown intent — return full list (safe fallback)
            return tools_text
        
        lines = tools_text.strip().split("\n")
        filtered = []
        for line in lines:
            # Always include chat.respond and memory.update
            if any(ai in line for ai in always_include):
                filtered.append(line)
                continue
            # Include tools matching the intent's prefixes
            if any(prefix in line for prefix in relevant_prefixes):
                filtered.append(line)
        
        return "\n".join(filtered) if filtered else tools_text

    def _select_best_tool(
        self, candidates: list[str], preference: str = "balanced"
    ) -> str:
        """Select the best tool from candidates based on preference (Phase E2.2).

        preference:
            - "balanced": highest cost_efficiency (quality / cost)
            - "speed": lowest estimated_latency_ms
            - "quality": highest quality_score
            - "cost": lowest estimated_cost_usd

        Returns the tool name. If no candidate has a manifest, returns the
        first candidate as a fallback.
        """
        manifests: list[tuple[str, ToolManifest]] = []
        for name in candidates:
            entry = self._registry.get(name)
            if entry is not None:
                manifests.append((name, entry.manifest))
        if not manifests:
            return candidates[0] if candidates else ""

        if preference == "speed":
            return min(manifests, key=lambda pair: pair[1].estimated_latency_ms)[0]
        if preference == "quality":
            return max(manifests, key=lambda pair: pair[1].quality_score)[0]
        if preference == "cost":
            return min(manifests, key=lambda pair: pair[1].estimated_cost_usd)[0]
        # balanced (default)
        return max(manifests, key=lambda pair: pair[1].cost_efficiency)[0]

    def _memory_summary(self, ctx: AIContext) -> str:
        """Brief categorised memory summary for the planner prompt.

        Shows per-category learning counts so the Planner knows what context
        is available without dumping every entry into the prompt.
        """
        counts = ctx.memory.counts_by_category()
        # Only include categories that actually have entries
        populated = {name: n for name, n in counts.items() if n > 0}
        parts: list[str] = []
        for name, n in populated.items():
            # Pretty label: "brand" -> "Brand"
            parts.append(f"{name.capitalize()}: {n} learning{'s' if n != 1 else ''}")
        if ctx.memory.total_campaigns:
            parts.append(f"{ctx.memory.total_campaigns} past campaigns")
        if ctx.memory.average_roi and ctx.memory.average_roi != "—":
            parts.append(f"avg ROI: {ctx.memory.average_roi}")
        return "; ".join(parts) if parts else "no memory yet"

    def _enriched_summary(self, ctx: AIContext) -> str:
        """Build a summary of enriched context (from Context Builder).

        This tells the Planner what business knowledge, MI outputs,
        integrations, and capabilities are available — so it can make
        better tool selection decisions.
        """
        parts: list[str] = []

        # Knowledge Hub
        if ctx.knowledge_chunks:
            parts.append(f"{len(ctx.knowledge_chunks)} knowledge chunks retrieved")

        # Marketing Intelligence
        mi = ctx.enriched.get("marketing_intelligence", {})
        if mi:
            mi_parts = []
            for key in ("business_profile", "audience_profile", "competitor_profile", "strategy"):
                if mi.get(key):
                    mi_parts.append(key.replace("_", " "))
            if mi_parts:
                parts.append(f"MI available: {', '.join(mi_parts)}")

        # Council memory
        council = ctx.enriched.get("council_memory", {})
        if council and council.get("recent_decisions"):
            parts.append(f"{len(council['recent_decisions'])} council decisions")

        # Integrations
        integrations = ctx.enriched.get("integrations", {})
        if integrations and integrations.get("connected"):
            names = [i["name"] for i in integrations["connected"]]
            parts.append(f"integrations: {', '.join(names)}")

        # Performance
        perf = ctx.enriched.get("performance", {})
        if perf and perf.get("campaign_performance"):
            parts.append("performance data available")

        # Reviews
        reviews = ctx.enriched.get("reviews", {})
        if reviews and reviews.get("pending_count", 0) > 0:
            parts.append(f"{reviews['pending_count']} pending reviews")

        # Capabilities
        if ctx.capabilities:
            avail = [c["name"] for c in ctx.capabilities if c.get("available")]
            if avail:
                parts.append(f"capabilities: {', '.join(avail[:8])}")

        if not parts:
            return ""
        return f" | Enriched: {'; '.join(parts)}"
