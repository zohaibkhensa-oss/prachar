"""Response Composer — composes conversational response from tool outputs.

Constitution Rule 9: CURV AI owns the conversation. Internal engines are invisible.
Users never see "CampaignBrain" or "Agency Council". They see CURV AI.

The Composer takes all tool outputs and produces a natural-language response
as if CURV AI did everything itself.
"""
from __future__ import annotations

import logging
from typing import Any

from prachar_shared.ai_gateway import AIGateway, Tier, extract_json_or_raise

from .context import AIContext
from .executor import ExecutionResult

log = logging.getLogger("prachar.runtime.composer")


COMPOSER_PROMPT = """\
You are CURV AI. You just completed a task for the user. Compose a \
natural, conversational response summarising what you did.

You are NOT a system reporter. You are a helpful AI marketing partner who \
happens to have just done some work. Speak in first person. Be warm, concise, \
and specific.

Rules:
- Never mention internal tool names, system components, or backend architecture
- Never use the words: "engine", "engines", "director", "directors", "node", \
"nodes", "pipeline", "DAG", "graph", "tool", "tools", "module", "service", \
"API", "endpoint", "registry", "executor", "planner", "runtime", "framework"
- Speak as "I" — "I analysed your business", "I created your campaign", \
"I reviewed it with my team"
- If a review happened, say "my team reviewed it" — never mention how many \
specialists, their roles, or that it's a "council"
- Include specific numbers from the results (confidence, budget, reach estimate)
- If approval is needed, ask for it naturally
- Keep it to 2-4 sentences unless the user asked for detail
- Be conversational, not technical. You are a marketing partner, not software.
- DO NOT copy the example format — generate a unique response based on the actual tool outputs

User's original request: {message}
Brand: {brand_name}
What was done (tool outputs):
{tool_outputs}

Respond as JSON with keys "reply", "summary", and "suggested_actions".
"""


class ResponseComposer:
    """Composes a conversational response from tool outputs.

    The user never sees tool names. They see CURV AI speaking naturally.
    """

    def __init__(self, gateway: AIGateway) -> None:
        self._gateway = gateway

    async def compose(
        self,
        ctx: AIContext,
        message: str,
        execution: ExecutionResult,
    ) -> dict[str, Any]:
        """Compose the final response from execution results.

        Returns:
            {
                "reply": "I've created your campaign...",
                "summary": "Campaign created, approved, ready to publish",
                "suggested_actions": ["Publish", "Show creatives"],
            }
        """
        brand_name = ctx.brand.name if ctx.brand else "your brand"

        # For conversation mode, the chat.respond tool already generated
        # a natural response — pass it through directly, no re-composition needed.
        outputs = execution.all_outputs()
        if "chat.respond" in outputs:
            chat_result = outputs["chat.respond"]
            if isinstance(chat_result, dict) and chat_result.get("reply"):
                return {
                    "reply": chat_result["reply"],
                    "summary": chat_result.get("summary", ""),
                    "suggested_actions": chat_result.get("suggested_actions", []),
                }

        # Format tool outputs for the prompt (truncate large outputs)
        tool_outputs = self._format_outputs(outputs)

        prompt = COMPOSER_PROMPT.format(
            message=message,
            brand_name=brand_name,
            tool_outputs=tool_outputs,
        )

        try:
            completion = await self._gateway.async_complete(
                prompt=prompt,
                tier=Tier.small,
                task="response_composer",
                tenant_id=str(ctx.tenant_id),
                plan=ctx.billing.plan,
                max_tokens=500,
                temperature=0.4,
            )
            data = extract_json_or_raise(completion.text)
            return {
                "reply": data.get("reply", "Done!"),
                "summary": data.get("summary", ""),
                "suggested_actions": data.get("suggested_actions", []),
            }
        except Exception as exc:
            log.warning("response composer failed: %s — using fallback", exc)
            return self._fallback_response(execution)

    def _format_outputs(self, outputs: dict[str, Any]) -> str:
        """Format tool outputs for the composer prompt (truncated)."""
        lines: list[str] = []
        for tool, output in outputs.items():
            # Truncate large outputs
            output_str = str(output)
            if len(output_str) > 500:
                output_str = output_str[:500] + "..."
            lines.append(f"[{tool}]: {output_str}")
        return "\n".join(lines) if lines else "(no tool outputs)"

    def _fallback_response(self, execution: ExecutionResult) -> dict[str, Any]:
        """Simple fallback if the composer LLM fails."""
        if execution.cancelled:
            return {
                "reply": "Okay, I've cancelled that.",
                "summary": "Cancelled",
                "suggested_actions": [],
            }
        if not execution.success:
            # Check for budget exceeded in warnings
            budget_warning = next(
                (w for w in execution.warnings if "budget exceeded" in w.lower()),
                None,
            )
            if budget_warning:
                return {
                    "reply": "I've reached your monthly AI usage limit. You can upgrade your plan in Settings → Billing to get more tokens, or try again next month when your quota resets.",
                    "summary": "Budget exceeded",
                    "suggested_actions": ["Upgrade plan", "View billing"],
                }
            return {
                "reply": f"I ran into an issue: {execution.error or 'something went wrong'}. Want me to try again?",
                "summary": "Error",
                "suggested_actions": ["Try again"],
            }
        tool_count = len([nr for nr in execution.node_results.values() if nr.success])
        return {
            "reply": f"All done! I completed {tool_count} steps for you.",
            "summary": f"{tool_count} steps completed",
            "suggested_actions": [],
        }
