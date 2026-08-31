"""
Intent Agent — lightweight tool pre-selection sub-agent.

Uses INTENT_MODEL (typically a smaller/faster model) to decide which tools
are needed before the main agent runs. Reduces latency for voice / real-time
use cases where tool selection by the large model would be too slow.

Only used when ChatAgentConfig.use_intent_agent = True.
"""
import json

from src.llm.base import LLMClient
from src.logger import get_logger
from src.tools.base import BaseTool

log = get_logger(__name__)


class IntentResult:
    def __init__(self, tools: list[str], reasoning: str) -> None:
        self.tools = tools
        self.reasoning = reasoning


class IntentAgent:
    def __init__(self, llm: LLMClient, system_prompt: str) -> None:
        self.llm = llm
        self.system_prompt = system_prompt

    async def run(
        self, user_message: str, available_tools: list[BaseTool]
    ) -> IntentResult:
        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in available_tools
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    f"Available tools:\n{tool_descriptions}\n\n"
                    f"User message: {user_message}"
                ),
            },
        ]

        response = await self.llm.chat(messages)
        content = (response.content or "").strip()

        try:
            # Strip markdown fences if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            parsed = json.loads(content)
            return IntentResult(
                tools=parsed.get("tools", []),
                reasoning=parsed.get("reasoning", ""),
            )
        except (json.JSONDecodeError, KeyError):
            log.warning("intent_agent.parse_failed", raw=content)
            # Fall back: use all tools
            return IntentResult(
                tools=[t.name for t in available_tools],
                reasoning="parse failed — using all tools",
            )
