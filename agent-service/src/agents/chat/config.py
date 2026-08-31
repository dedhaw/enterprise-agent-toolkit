from pathlib import Path

from src.tools.get_time import GetTimeTool

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


class ChatAgentConfig:
    # Which tools this agent can use
    tools = [GetTimeTool()]

    # Set to True to enable the intent agent (tool pre-selection via a smaller model)
    # Useful for voice / low-latency use cases. For most cases the main LLM handles this.
    use_intent_agent: bool = True

    # Prompts — loaded from markdown files at import time
    system_prompt: str = _load_prompt("chat_master_prompt.md")
    intent_agent_prompt: str = _load_prompt("intent_agent_prompt.md")

    # Memory: sliding window — max turns sent to LLM per request
    max_history_turns: int = 20

    # Memory: compacting — summarize old turns when session exceeds this threshold
    compact_after_turns: int = 30   # total turns before compaction fires
    compact_recent_turns: int = 10  # full turns to keep after the summary
