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
    use_intent_agent: bool = False

    # Prompts — loaded from markdown files at import time
    system_prompt: str = _load_prompt("chat_master_prompt.md")
    intent_agent_prompt: str = _load_prompt("intent_agent_prompt.md")

    # Max turns to include in each request (sliding window for long sessions)
    max_history_turns: int = 20
