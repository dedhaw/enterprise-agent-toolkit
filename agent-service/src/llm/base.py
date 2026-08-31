from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMClient(ABC):
    model: str

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> LLMResponse:
        """
        Send a chat request and return an LLMResponse.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            tools:    Optional list of OpenAI-format tool schemas.
            stream:   If True, stream the response (not yet implemented in all clients).
        """
