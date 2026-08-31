"""
Azure OpenAI client stub.
Install: pip install openai
"""
from src.llm.base import LLMClient, LLMResponse


class AzureOpenAIClient(LLMClient):
    def __init__(self, endpoint: str, api_key: str, api_version: str, model: str) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_version = api_version
        self.model = model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> LLMResponse:
        # TODO: implement with `openai` package
        # from openai import AsyncAzureOpenAI
        # client = AsyncAzureOpenAI(
        #     azure_endpoint=self.endpoint,
        #     api_key=self.api_key,
        #     api_version=self.api_version,
        # )
        # response = await client.chat.completions.create(
        #     model=self.model, messages=messages, tools=tools
        # )
        raise NotImplementedError("Azure OpenAI client not yet implemented")
