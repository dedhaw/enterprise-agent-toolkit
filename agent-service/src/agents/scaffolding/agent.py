"""
Scaffolding Agent — template agent loop.

This mirrors the structure of src/agents/chat/chat.py.

Memory strategy is configurable — see the MEMORY STRATEGY section below.
Two options are shown:
  - SlidingWindowMemory  (simple, fixed token cost)
  - CompactingMemory     (uses a small LLM to summarize old turns)
"""
import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.agents.scaffolding.config import ScaffoldingAgentConfig
from src.agents.scaffolding.memory import CompactingMemory, SlidingWindowMemory
from src.config import get_llm_client, get_settings
from src.llm.base import LLMClient
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class ScaffoldingAgentResponse:
    reply: str
    session_id: str
    tools_used: list[str] = field(default_factory=list)


class ScaffoldingAgent:
    def __init__(self, db_session: Session) -> None:
        self.config = ScaffoldingAgentConfig()
        self.llm: LLMClient = get_llm_client(get_settings().general_model)
        self._tool_map = {t.name: t for t in self.config.tools}

        # ── MEMORY STRATEGY ───────────────────────────────────────────────────
        # Pick one. Comment out the other.
        #
        # Option A: Sliding window — last N turns only, simple and cheap.
        self.memory = SlidingWindowMemory(db_session, max_turns=20)
        #
        # Option B: Compacting — summarizes old turns when session gets long.
        # Uses a separate LLM call (use a fast/cheap model for the summarizer).
        # Uncomment to use:
        #
        # summarizer_llm = get_llm_client(get_settings().intent_model)
        # self.memory = CompactingMemory(
        #     db_session,
        #     llm=summarizer_llm,
        #     recent_turns=10,        # keep last 10 turns in full after summary
        #     compact_after_turns=30, # summarize when total turns exceed this
        # )
        # ─────────────────────────────────────────────────────────────────────

    async def run(self, session_id: str, user_message: str) -> ScaffoldingAgentResponse:
        log.info("scaffolding_agent.run", session_id=session_id)

        # ── Step A: load history ──────────────────────────────────────────────
        # SlidingWindowMemory.load() is sync. CompactingMemory.load() is async
        # because it may call the LLM to summarize. Handle both:
        if isinstance(self.memory, CompactingMemory):
            history = await self.memory.load(session_id)
        else:
            history = self.memory.load(session_id)

        # ── Step B: build messages ────────────────────────────────────────────
        messages = [
            {"role": "system", "content": self.config.system_prompt},
            *history,
            {"role": "user", "content": user_message},
        ]

        # ── Step C: prepare tool schemas ──────────────────────────────────────
        tool_schemas = [t.to_openai_schema() for t in self.config.tools] or None

        # ── Step D: first LLM call ────────────────────────────────────────────
        response = await self.llm.chat(messages, tools=tool_schemas)

        # Handle models that return empty content when tools are present but not needed
        if not response.content and not response.tool_calls and tool_schemas:
            response = await self.llm.chat(messages, tools=None)

        tools_used: list[str] = []

        # ── Step E: tool execution loop ───────────────────────────────────────
        if response.tool_calls:
            known_calls = [tc for tc in response.tool_calls if tc.name in self._tool_map]
            unknown_calls = [tc.name for tc in response.tool_calls if tc.name not in self._tool_map]

            if unknown_calls:
                log.warning("scaffolding_agent.unknown_tools", names=unknown_calls)

            if known_calls:
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in known_calls
                    ],
                })

                for tc in known_calls:
                    tool = self._tool_map.get(tc.name)
                    if tool:
                        result = await tool.execute(**tc.arguments)
                        tools_used.append(tc.name)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": str(result.data) if result.success else f"Error: {result.error}",
                        })

                response = await self.llm.chat(messages)
            else:
                response = await self.llm.chat(messages, tools=None)

        final_reply = response.content or ""

        # ── Step F: save turn ─────────────────────────────────────────────────
        self.memory.save(session_id, user_message, final_reply)

        return ScaffoldingAgentResponse(
            reply=final_reply,
            session_id=session_id,
            tools_used=tools_used,
        )
