from enum import Enum
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppMode(str, Enum):
    local = "local"
    test = "test"
    prod = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_mode: AppMode = AppMode.prod

    # ── Models ───────────────────────────────────────────────────────────────
    general_model: str = "qwen3:4b"
    intent_model: str = "qwen3:4b"

    # ── Ollama (local) ────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"

    # ── Azure OpenAI (test / prod) ────────────────────────────────────────────
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-02-01"

    # ── AWS Bedrock (test / prod) ─────────────────────────────────────────────
    aws_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # ── Database ──────────────────────────────────────────────────────────────
    db_path: str = "./data/agent.db"
    chroma_path: str = "./data/chromadb"

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_service_url: str = ""

    @model_validator(mode="after")
    def validate_cloud_credentials(self) -> "Settings":
        if self.app_mode == AppMode.local:
            return self
        has_azure = bool(self.azure_openai_api_key and self.azure_openai_endpoint)
        has_aws = bool(self.aws_access_key_id and self.aws_secret_access_key)
        if not has_azure and not has_aws:
            raise ValueError(
                f"APP_MODE={self.app_mode} requires Azure OpenAI or AWS Bedrock credentials"
            )
        return self

    @property
    def active_cloud(self) -> str:
        """Returns which cloud provider to use in test/prod."""
        if self.azure_openai_api_key and self.azure_openai_endpoint:
            return "azure"
        return "aws"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_llm_client(model: str | None = None):
    """
    Factory: returns the right LLM client for the current APP_MODE.
    Import here to avoid circular deps.
    """
    from src.llm.ollama import OllamaClient
    from src.llm.azure import AzureOpenAIClient
    from src.llm.aws import AWSBedrockClient

    settings = get_settings()
    resolved_model = model or settings.general_model

    if settings.app_mode == AppMode.local:
        return OllamaClient(base_url=settings.ollama_base_url, model=resolved_model)
    if settings.active_cloud == "azure":
        return AzureOpenAIClient(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            model=resolved_model,
        )
    return AWSBedrockClient(
        region=settings.aws_region,
        access_key_id=settings.aws_access_key_id,
        secret_access_key=settings.aws_secret_access_key,
        model=resolved_model,
    )
