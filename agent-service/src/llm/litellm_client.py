"""
LiteLLM client — calls the OpenAI-compatible /v1/chat/completions endpoint.
Used in prod mode when the Intel infra stack is running (LiteLLM on port 4000).
"""
import json
import uuid

import httpx

from src.llm.base import LLMClient, LLMResponse, ToolCall
from src.logger import get_logger

log = get_logger(__name__)


class LiteLLMClient(LLMClient):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
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
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        log.debug("litellm.chat", model=self.model, message_count=len(messages))

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        message = data["choices"][0]["message"]
        content = message.get("content") or None
        raw_tool_calls = message.get("tool_calls") or []

        tool_calls = [
            ToolCall(
                id=tc.get("id") or str(uuid.uuid4()),
                name=tc["function"]["name"],
                # OpenAI format: arguments is a JSON string, not a dict
                arguments=json.loads(tc["function"].get("arguments") or "{}"),
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
