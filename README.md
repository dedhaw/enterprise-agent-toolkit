# Enterprise Agent Toolkit

A monorepo for building and deploying production AI agents. Contains the agent service, frontend, and the infrastructure platform that runs it all.

---

## What's in here

```
enterprise-agent-toolkit/
├── agent-service/     Python FastAPI agent backend — build agents here
├── frontend/          React chatbot UI
├── agent-infra/             Platform infrastructure (K8s, Docker Compose, LiteLLM, Flowise, observability)
└── Makefile           Top-level orchestration
```

---

## Quick Start (local dev)

```bash
# 1. Start the agent service
cd agent-service
make install
make dev              # → http://localhost:8000

# 2. Start the frontend (separate terminal)
cd frontend
npm install
npm run dev           # → http://localhost:5173

# 3. Full platform stack (optional — needs Docker)
make run              # starts Ollama + Docker services + frontend
```

---

## Development workflow

**Building agents** → work in `agent-service/`
- Add tools in `src/tools/`
- Add agents in `src/agents/`
- New API versions in `src/api/`

**Changing the UI** → work in `frontend/`

**Deploying the platform** → work in `agent-infra/`
- Docker Compose: `agent-infra/docker/`
- Kubernetes: `agent-infra/core/`
- `agent-infra/deploy-agentic-stack.sh`

---

## Environments

| Mode | LLM Backend | How to run |
|---|---|---|
| `local` | Ollama on your machine | `APP_MODE=local` in `agent-service/.env` |
| `test` | Azure OpenAI or AWS Bedrock | `APP_MODE=test` + cloud credentials |
| `prod` | Azure OpenAI or AWS Bedrock + full infra stack | `APP_MODE=prod` + deploy infra |

---

## How agent-service connects to infra (prod)

The platform in `agent-infra/` provides the backends `agent-service` uses in production:

| Infra service | What agent-service uses it for |
|---|---|
| LiteLLM (port 4000) | LLM gateway — set as `OLLAMA_BASE_URL` equivalent in prod |
| PostgreSQL (port 5432) | Replace SQLite with shared Postgres |
| Redis (port 6379) | Session caching |
| Langfuse (port 3002) | LLM call tracing via `LOG_SERVICE_URL` |
| Kubernetes | Deploy `agent-service/k8s/` manifests |

See `agent-infra/README.md` for the original platform documentation and `report.md` for context on what the infra was originally built for.
