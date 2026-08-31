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
    │   └── chat/           # Chat agent
    │       ├── config.py   # Tool list, model, intent agent flag, loads prompts
    │       ├── chat.py     # Agent loop
    │       ├── intent_agent.py  # Lightweight tool-selection sub-agent
    │       ├── prompts/    # Markdown prompt files
    │       └── memory/
    │           ├── conversation.py  # SQLite-backed session history
    │           └── vector_store.py  # ChromaDB semantic search / RAG
    ├── routes/
    │   └── chat_router.py  # POST /message, GET /history/{session_id}
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
| `local` | Ollama | Development on your machine |
| `test` | Azure OpenAI or AWS Bedrock | Integration / staging |
| `prod` | Azure OpenAI or AWS Bedrock | Production |

Config auto-selects the right LLM client. For `test`/`prod`, set either Azure or AWS credentials — whichever is present wins.

---

## Adding a Tool

1. Create `src/tools/<tool_name>.py`, subclass `BaseTool`
2. Set `name`, `description` (the LLM prompt), `parameters` (JSON Schema)
3. Implement `async def execute(**kwargs) -> ToolResult`
4. Add it to the agent's `config.py` tools list

---

## Adding an Agent

1. Create `src/agents/<agent_name>/` with the same structure as `chat/`
2. Create `src/routes/<agent_name>_router.py`
3. Include it in the target API version: `src/api/v0/router.py`

---

## API Versioning

Each `src/api/<version>/router.py` is a frozen contract. When a change would break existing callers:
- Create `src/api/v1/router.py`
- Add new/changed routes there
- Old `v0` routes remain unchanged

---

## Intent Agent

The intent agent is a lightweight sub-agent that pre-selects which tools to invoke before the main LLM runs. It trades one extra LLM call for faster main-model inference (fewer tools = smaller context = faster).

Enable per agent in `agents/<name>/config.py`:
```python
use_intent_agent: bool = True
```

Best for: voice agents, real-time applications, agents with many tools.
For most chat agents, the main LLM handles tool selection directly.
