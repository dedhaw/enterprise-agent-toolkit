"""
Scaffolding Agent Config — template for building a new agent.

Steps to create a real agent from this scaffold:
  1. Rename this folder: src/agents/<your_agent_name>/
  2. Edit prompts/system_prompt.md with your agent's persona and rules
  3. Add tools to the `tools` list below (import from src/tools/ or create new ones)
  4. Set use_intent_agent=True if your agent has many tools and needs low latency
  5. Create src/routes/<your_agent_name>_router.py (copy scaffolding_router.py)
  6. Register the route in src/api/v0/router.py
"""
from pathlib import Path

# ── Step 3: import your tools here ───────────────────────────────────────────
# from src.tools.get_time import GetTimeTool
# from src.tools.your_tool import YourTool

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


class ScaffoldingAgentConfig:
    # ── Step 3: add your tools here ───────────────────────────────────────────
    # tools = [GetTimeTool(), YourTool()]
    tools = []  # no tools by default — the agent answers from its system prompt only

    # ── Step 4: enable intent agent for low-latency / many-tool scenarios ─────
    # The intent agent runs a lightweight LLM call first to select which tools
    # are relevant before the main LLM runs. Costs one extra LLM call but
    # reduces context size and speeds up the main call when you have many tools.
    use_intent_agent: bool = False

    # ── Step 2: edit your system prompt ──────────────────────────────────────
    system_prompt: str = _load_prompt("system_prompt.md")

    # Intent agent prompt (only used when use_intent_agent=True)
    # The intent agent needs to know what tools are available and pick the right ones.
    # You can reuse the chat agent's intent prompt or write your own.
    intent_agent_prompt: str = (
        "You are a tool selector. Given a user message and a list of available tools, "
        "return a JSON object with a 'tools' key listing the tool names that are relevant. "
        "Return an empty list if no tools are needed."
    )

    # How many past turns to include in each request (sliding window)
    max_history_turns: int = 20
