import uuid

import httpx

from src.llm.base import LLMClient, LLMResponse, ToolCall
from src.logger import get_logger

log = get_logger(__name__)


class OllamaClient(LLMClient):
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,  # streaming handled separately when needed
        }
        if tools:
            payload["tools"] = tools

        log.debug("ollama.chat", model=self.model, message_count=len(messages))

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message", {})
        content = message.get("content") or None
        raw_tool_calls = message.get("tool_calls") or []

        tool_calls = [
            ToolCall(
                id=str(uuid.uuid4()),
                name=tc["function"]["name"],
                arguments=tc["function"].get("arguments", {}),
            )
            for tc in raw_tool_calls
        ]

        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            tool_calls=tool_calls or None,
            model=data.get("model", self.model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
