"""
Langfuse tracing wrapper.
No-op when LANGFUSE_PUBLIC_KEY is not configured so local mode works unchanged.
"""
from __future__ import annotations

from src.logger import get_logger

log = get_logger(__name__)


class Tracer:
    """Wraps Langfuse tracing. All methods are no-ops if Langfuse is not configured."""

    def __init__(self) -> None:
        from src.config import get_settings
        settings = get_settings()
        self._enabled = bool(settings.langfuse_public_key and settings.langfuse_secret_key)
        self._client = None

        if self._enabled:
            try:
                from langfuse import Langfuse
                self._client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
                log.info("tracing.enabled", host=settings.langfuse_host)
            except Exception as e:
                log.warning("tracing.init_failed", error=str(e))
                self._enabled = False

    def trace(self, name: str, session_id: str, user_input: str):
        if not self._enabled or not self._client:
            return _NoOpTrace()
        return _LangfuseTrace(self._client.trace(
            name=name,
            session_id=session_id,
            input=user_input,
        ))

    def flush(self) -> None:
        if self._enabled and self._client:
            self._client.flush()


class _NoOpTrace:
    def generation(self, **_):
        return _NoOpGeneration()

    def update(self, **_):
        pass


class _NoOpGeneration:
    def end(self, **_):
        pass


class _LangfuseTrace:
    def __init__(self, trace) -> None:
        self._trace = trace

    def generation(self, name: str, model: str, messages: list[dict]):
        return _LangfuseGeneration(self._trace.generation(
            name=name,
            model=model,
            input=messages,
        ))

    def update(self, output: str, tools_used: list[str]) -> None:
        self._trace.update(output=output, metadata={"tools_used": tools_used})


class _LangfuseGeneration:
    def __init__(self, gen) -> None:
        self._gen = gen

    def end(self, content: str | None, prompt_tokens: int, completion_tokens: int) -> None:
        self._gen.end(
            output=content,
            usage={"input": prompt_tokens, "output": completion_tokens},
        )
