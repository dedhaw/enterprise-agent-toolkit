# Agent Service

FastAPI-based agent backend. Supports multiple agents, versioned APIs, pluggable tools, multi-model environments, and semantic memory.

---

## Quick Start

```bash
cp .env.example .env   # edit APP_MODE, models, etc.
make install
make dev               # http://localhost:8000
```

Test it:
```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/api/v0/agents/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test1", "message": "what time is it?"}'

curl http://localhost:8000/api/v0/agents/chat/history/test1
```

Interactive docs: `http://localhost:8000/docs`

---

## Structure

```
agent-service/
├── .env                    # environment config (not committed)
├── .env.example            # documented template
├── requirements.txt
├── Makefile                # install / run / dev / clean
├── Dockerfile
├── docker-compose.yml
├── k8s/                    # Kubernetes manifests
└── src/
    ├── app.py              # FastAPI app entry point
    ├── config.py           # Settings (pydantic-settings), LLM factory
    ├── logger.py           # Structured logging (structlog)
    ├── llm/                # LLM client abstraction
    │   ├── base.py         # Abstract LLMClient + LLMResponse models
    │   ├── ollama.py       # Ollama (local)
    │   ├── azure.py        # Azure OpenAI (stub)
    │   └── aws.py          # AWS Bedrock (stub)
    ├── tools/              # Agent tools
    │   ├── base.py         # BaseTool ABC — description IS the tool prompt
    │   └── get_time.py     # Example: returns current time
    ├── agents/
    │   ├── chat/                    # Production chat agent
    │   │   ├── config.py            # Tool list, intent agent flag, loads prompts
    │   │   ├── chat.py              # Agent loop
    │   │   ├── intent_agent.py      # Lightweight tool-selection sub-agent
    │   │   ├── prompts/             # Markdown prompt files
    │   │   └── memory/
    │   │       ├── conversation.py  # Session history (Postgres / SQLite)
    │   │       └── vector_store.py  # ChromaDB semantic search / RAG
    │   └── scaffolding/             # Template — copy this to build a new agent
    │       ├── config.py            # Annotated config with all options explained
    │       ├── agent.py             # Agent loop with memory strategy toggle
    │       ├── memory.py            # SlidingWindowMemory + CompactingMemory
    │       └── prompts/
    │           └── system_prompt.md # Placeholder prompt with writing tips
    ├── routes/
    │   ├── chat_router.py           # POST /message, GET /history/{session_id}
    │   └── scaffolding_router.py    # Template router (copy for new agents)
    ├── api/
    │   └── v0/
    │       └── router.py   # Mounts all v0 routes
    └── db/
        ├── base.py         # SQLAlchemy engine + session factory
        └── chat/
            └── models.py   # ChatSession, ChatMessage ORM models
```

---

## Environment Modes

| `APP_MODE` | LLM Client | Use Case |
|---|---|---|
| `local` | Ollama direct | Development on your machine |
| `test` | Azure OpenAI or AWS Bedrock | Integration / staging |
| `prod` | LiteLLM gateway → Ollama / any model | Full Intel infra stack |

In `prod` mode, set `LITELLM_API_KEY` to route through the LiteLLM gateway (auth, rate limiting, model routing). If `LITELLM_API_KEY` is not set, it falls back to Azure or AWS credentials.

---

## Adding a Tool

1. Create `src/tools/<tool_name>.py`, subclass `BaseTool`
2. Set `name`, `description` (the LLM prompt), `parameters` (JSON Schema)
3. Implement `async def execute(**kwargs) -> ToolResult`
4. Add it to the agent's `config.py` tools list

---

## Adding an Agent

Use `src/agents/scaffolding/` as your starting point — it's a fully commented template.

1. Copy `src/agents/scaffolding/` → `src/agents/<your_agent>/`
2. Edit `prompts/system_prompt.md` with your agent's persona and rules
3. Add tools to `config.py`
4. Copy `src/routes/scaffolding_router.py` → `src/routes/<your_agent>_router.py` and update the import
5. Register the router in `src/api/v0/router.py`

---

## API Versioning

Each `src/api/<version>/router.py` is a frozen contract. When a change would break existing callers:
- Create `src/api/v1/router.py`
- Add new/changed routes there
- Old `v0` routes remain unchanged

---

## Intent Agent

The intent agent is a lightweight sub-agent that pre-selects which tools to invoke before the main LLM runs. It trades one extra LLM call for faster main-model inference (fewer tools = smaller context = faster). It also prevents small models from calling tools unnecessarily on simple messages like greetings.

Enable per agent in `agents/<name>/config.py`:
```python
use_intent_agent: bool = True
```

Best for: voice agents, real-time applications, agents with many tools, or when using smaller models prone to over-calling tools.

---

## Memory Strategies

Conversation history is stored per `session_id` in Postgres (prod) or SQLite (local). Two strategies are available — see `src/agents/scaffolding/memory.py` for full implementation.

### Sliding Window
Keeps the last N turns. Older turns fall out of context but remain in the DB.

```python
# agents/<name>/config.py
max_history_turns: int = 20  # last 20 user+assistant pairs
```

- Token cost: fixed
- Agent forgets things before the window
- Best for: short tasks, Q&A, support bots

### Compacting
When total turns exceed a threshold, a small LLM summarizes the old turns. The summary + recent full turns are sent to the main LLM — the agent never loses early context.

```python
from src.agents.scaffolding.memory import CompactingMemory

summarizer_llm = get_llm_client(get_settings().intent_model)
self.memory = CompactingMemory(
    db_session,
    llm=summarizer_llm,
    recent_turns=10,        # full turns kept after the summary
    compact_after_turns=30, # total turns before compaction fires
)
```

- Token cost: variable (one extra LLM call when compaction fires)
- Agent retains gist of the entire conversation
- Best for: long sessions, onboarding flows, anything needing early context
