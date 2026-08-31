from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    data: Any
    error: str | None = None
    call_id: str = ""


class BaseTool(ABC):
    # Subclasses must define these
    name: str
    description: str  # shown to the LLM — this IS the tool prompt
    parameters: dict  # JSON Schema for the tool's arguments

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Run the tool and return a ToolResult."""

    def to_openai_schema(self) -> dict:
        """Returns the OpenAI function-calling schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
