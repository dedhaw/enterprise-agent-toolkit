"""
AWS Bedrock client stub.
Install: pip install boto3
"""
from src.llm.base import LLMClient, LLMResponse


class AWSBedrockClient(LLMClient):
    def __init__(self, region: str, access_key_id: str, secret_access_key: str, model: str) -> None:
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.model = model

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> LLMResponse:
        # TODO: implement with boto3 + bedrock-runtime
        # import boto3, json
        # client = boto3.client(
        #     "bedrock-runtime",
        #     region_name=self.region,
        #     aws_access_key_id=self.access_key_id,
        #     aws_secret_access_key=self.secret_access_key,
        # )
        raise NotImplementedError("AWS Bedrock client not yet implemented")
