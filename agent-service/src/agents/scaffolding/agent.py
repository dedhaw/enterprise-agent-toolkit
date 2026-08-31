"""
Scaffolding Agent — template agent loop.

This mirrors the structure of src/agents/chat/chat.py.
The agent loop here is intentionally minimal — no memory, no vector store —
to show the bare minimum needed to get an agent responding.

To add memory: see src/agents/chat/memory/conversation.py
To add semantic search: see src/agents/chat/memory/vector_store.py
"""
import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.agents.scaffolding.config import ScaffoldingAgentConfig
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
        # db_session is available if you want to add memory later
        self.db_session = db_session
        self.config = ScaffoldingAgentConfig()
        self.llm: LLMClient = get_llm_client(get_settings().general_model)
        self._tool_map = {t.name: t for t in self.config.tools}

    async def run(self, session_id: str, user_message: str) -> ScaffoldingAgentResponse:
        log.info("scaffolding_agent.run", session_id=session_id)

        # ── Step A: build the message list ───────────────────────────────────
        # In a real agent, load history from memory here and prepend it.
        # See ConversationMemory in src/agents/chat/memory/conversation.py
        messages = [
            {"role": "system", "content": self.config.system_prompt},
            # history would go here
            {"role": "user", "content": user_message},
        ]

        # ── Step B: prepare tool schemas ──────────────────────────────────────
        tool_schemas = [t.to_openai_schema() for t in self.config.tools] or None

        # ── Step C: first LLM call ────────────────────────────────────────────
        response = await self.llm.chat(messages, tools=tool_schemas)

        # Handle models that return empty content when tools are present but not needed
        if not response.content and not response.tool_calls and tool_schemas:
            response = await self.llm.chat(messages, tools=None)

        tools_used: list[str] = []

        # ── Step D: tool execution loop ───────────────────────────────────────
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

                # Final LLM call with tool results
                response = await self.llm.chat(messages)
            else:
                response = await self.llm.chat(messages, tools=None)

        # ── Step E: save to memory ────────────────────────────────────────────
        # Add memory persistence here when ready. Example:
        #   self.memory.save_turn(session_id, user_message, response.content or "")

        return ScaffoldingAgentResponse(
            reply=response.content or "",
            session_id=session_id,
            tools_used=tools_used,
        )
