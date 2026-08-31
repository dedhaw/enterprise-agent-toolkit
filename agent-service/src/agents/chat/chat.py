"""
Chat Agent — the main agent loop.

Flow:
  1. Load conversation history from SQLite
  2. Optionally run intent agent to select tools (if use_intent_agent=True)
  3. Call the main LLM with system prompt + history + user message + tools
  4. If the LLM requests tool calls → execute them → send results back to LLM
  5. Save the turn to memory
  6. Return the final reply
"""
import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.agents.chat.config import ChatAgentConfig
from src.agents.chat.intent_agent import IntentAgent
from src.agents.chat.memory.conversation import ConversationMemory
from src.agents.chat.memory.vector_store import VectorStore
from src.config import get_llm_client, get_settings
from src.llm.base import LLMClient
from src.logger import get_logger
from src.tools.base import BaseTool
from src.tracing import Tracer

log = get_logger(__name__)
_tracer = Tracer()


@dataclass
class AgentResponse:
    reply: str
    tools_used: list[str] = field(default_factory=list)
    session_id: str = ""


class ChatAgent:
    def __init__(self, db_session: Session) -> None:
        settings = get_settings()
        self.config = ChatAgentConfig()
        self.llm: LLMClient = get_llm_client(settings.general_model)
        self.memory = ConversationMemory(db_session)
        self.vector_store = VectorStore(settings.chroma_path)

        self._tool_map: dict[str, BaseTool] = {t.name: t for t in self.config.tools}

        if self.config.use_intent_agent:
            intent_llm = get_llm_client(settings.intent_model)
            self.intent_agent = IntentAgent(intent_llm, self.config.intent_agent_prompt)
        else:
            self.intent_agent = None

    async def run(self, session_id: str, user_message: str) -> AgentResponse:
        log.info("agent.run", session_id=session_id)
        trace = _tracer.trace(name="chat-agent", session_id=session_id, user_input=user_message)

        # 1. Load history
        history = self.memory.load_history(session_id, self.config.max_history_turns)

        # 2. Determine which tools to offer the LLM
        active_tools = list(self.config.tools)
        if self.intent_agent:
            intent = await self.intent_agent.run(user_message, active_tools)
            active_tools = [t for t in active_tools if t.name in intent.tools]
            log.debug("intent.selected", tools=intent.tools, reasoning=intent.reasoning)

        tool_schemas = [t.to_openai_schema() for t in active_tools] if active_tools else None

        # 3. Build message list
        messages = (
            [{"role": "system", "content": self.config.system_prompt}]
            + history
            + [{"role": "user", "content": user_message}]
        )

        # 4. First LLM call
        generation = trace.generation(name="llm-call", model=self.llm.model, messages=messages)
        response = await self.llm.chat(messages, tools=tool_schemas)
        generation.end(
            content=response.content,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )

        # Some smaller models return empty content when tools are present but not needed.
        # Fall back to a call without tools to get a natural language response.
        if not response.content and not response.tool_calls and tool_schemas:
            log.debug("agent.empty_response_with_tools — retrying without tools")
            response = await self.llm.chat(messages, tools=None)

        tools_used: list[str] = []

        # 5. Tool execution loop
        if response.tool_calls:
            messages.append({
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in response.tool_calls
                ],
            })

            for tc in response.tool_calls:
                tool = self._tool_map.get(tc.name)
                if not tool:
                    log.warning("agent.unknown_tool", name=tc.name)
                    continue

                result = await tool.execute(**tc.arguments)
                result.call_id = tc.id
                tools_used.append(tc.name)
                log.debug("tool.executed", name=tc.name, success=result.success)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result.data) if result.success else f"Error: {result.error}",
                })

            # Final LLM call with tool results
            final_gen = trace.generation(name="llm-call-with-tools", model=self.llm.model, messages=messages)
            response = await self.llm.chat(messages)
            final_gen.end(
                content=response.content,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            )

        final_reply = response.content or ""

        # 6. Persist to memory
        self.memory.save_turn(session_id, user_message, final_reply)
        turn_id = str(uuid.uuid4())
        self.vector_store.add(session_id, turn_id, f"User: {user_message}\nAssistant: {final_reply}")

        trace.update(output=final_reply, tools_used=tools_used)
        _tracer.flush()

        return AgentResponse(reply=final_reply, tools_used=tools_used, session_id=session_id)
