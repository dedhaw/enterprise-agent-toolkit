# What This Repo Was Originally

## Origin

This repository started as the **Intel® AI for Enterprise Agent Toolkit** — an open-source project by Intel Corporation (Apache 2.0) designed to solve one specific problem: the infrastructure complexity of deploying agentic AI systems on enterprise hardware.

The original repo is at `github.com/intel/enterprise-agent-toolkit`. Everything in `agent-infra/` is that original project, preserved as-is.

---

## What it was built to do

The toolkit is a **deployment platform**, not an agent framework. Intel's goal was to let enterprises spin up a production-ready AI infrastructure stack in hours rather than months. It does not contain any agent logic, prompts, or business rules — those are left entirely to the user.

It provisions and wires together the following open-source components:

| Component | Role |
|---|---|
| **LiteLLM** | OpenAI-compatible API gateway — unified entry point for all LLM traffic, auth, rate limiting |
| **vLLM / SGLang** | LLM inference servers, optimized for Intel Xeon CPUs with AMX acceleration |
| **Redis Stack** | Short-term agent memory, session context, job queues |
| **PostgreSQL + pgvector** | Long-term memory, vector similarity search, RAG |
| **Flowise** | Visual no-code agent builder — where users could define workflows without writing code |
| **Langfuse** | LLM observability — traces every token, latency, and agent step |
| **Agent Sandbox** | Ephemeral Kubernetes pods for safe agent code execution |
| **KubeRay** | Distributed computing for parallel tool calling |
| **Prometheus + Grafana + Loki** | System metrics, dashboards, log aggregation |

Deployment targets: **Kubernetes** (via Kubespray on bare-metal Intel Xeon) and **Docker Compose** (for local and demo use).

---

## What it was NOT

- **Not an agent service.** There is no Python code, no agent loop, no tool definitions, no system prompts. The infra gives you the platform; you bring the agents.
- **Not cloud-native by design.** It was built for on-prem Intel Xeon servers and air-gapped environments. The Kubernetes setup uses Kubespray targeting bare metal, not EKS/AKS/GKE (though the services themselves are portable once a cluster exists).
- **Not model-specific.** LiteLLM abstracts over any model — OpenAI, Anthropic, Gemini, local vLLM, Ollama. The toolkit ships with Intel-optimized CPU inference configs (Qwen, Llama, Gemma) but is model-agnostic.

---

## The key insight Intel was solving for

> GPUs accelerate reasoning. But the *value* of agentic AI comes from end-to-end task execution — and that control plane (state, tools, policy, coordination) runs efficiently on CPUs.

The toolkit was built around this: run inference on Intel Xeon (no expensive GPU required), and wrap it with enterprise-grade governance, memory, and observability. The target customer was an enterprise IT team that wanted to run private AI internally without cloud dependency.

---

## How this fork extends it

This repo takes the Intel platform and adds what it was always missing: the actual agent layer.

```
agent-infra/          ← Intel's original toolkit (unchanged)
agent-service/        ← FastAPI agent service built on top of it
frontend/             ← React chatbot UI for testing
```

`agent-service` is designed to run standalone locally (talking directly to Ollama) and to slot into the full infra platform in production — using LiteLLM as its gateway, Postgres/Redis as its data layer, and Langfuse for tracing.

The infra is the stage. `agent-service` is what performs on it.

---

## The infra in detail — what's running and why

When you run `make run`, Docker starts the following services. Here is what each one does and why you'd care.

### LiteLLM — `http://localhost:4000`

> **Proxy and routing layer. Every service talks to one endpoint — swap the model in one config file and nothing else changes. Gives you per-key auth, rate limits, and budget controls across every agent and service sharing the same LLM.**

**What it is:** An OpenAI-compatible reverse proxy that sits in front of your actual LLM.

**What it does:** Instead of your agent calling Ollama or any cloud model directly, every LLM request goes through LiteLLM first. It handles:
- **Auth** — virtual API keys so different services can have different access levels
- **Rate limiting** — prevent any one service from monopolizing the model
- **Model routing** — swap the underlying model (Ollama → Azure → AWS) without changing any agent code
- **Usage logging** — every call is logged to Postgres and forwarded to Langfuse

**Login / UI:** LiteLLM has no web UI in open-source mode. You manage it via its REST API or by editing `agent-infra/docker/litellm/config.yaml`. The master key is `sk-6a6f751b5716bff7a396` (from `agent-infra/docker/.env`).

**Why use it vs calling Ollama directly:** In production you may run multiple agents, multiple services, or multiple team members all hitting the same LLM. LiteLLM is the single controlled entrypoint — you can rotate keys, swap models, set budgets, and see all traffic in one place without touching agent code.

---

### PostgreSQL + pgvector — `localhost:5432`

**What it is:** A single shared Postgres instance with the `pgvector` extension enabled for vector similarity search.

**What it does:** Hosts four separate databases:
| Database | Owner | Used for |
|---|---|---|
| `litellm` | `litellm` user | LiteLLM stores API keys, usage records, model configs |
| `flowisedb` | `flowise` user | Flowise stores agent workflows, credentials, chat logs |
| `langfuse` | `langfuse` user | Langfuse stores traces, scores, prompts |
| `agentdb` | `agentuser` | Your agent-service — conversation history, vector embeddings |

**No login UI** — connect with any Postgres client (e.g. TablePlus, psql) using the credentials from `agent-infra/docker/.env`. The `agentdb` user/password is `agentuser` / `wLsx5AxhuBxdbXKRQv4L`.

**Why use it vs SQLite:** SQLite is a single-file DB local to the process — fine for dev on one machine. Postgres is networked, shared, and durable. In production: multiple agent-service instances can share the same conversation history, you can run analytics queries across sessions, and pgvector lets you do semantic search at scale without a separate vector DB.

---

### Redis Stack — `localhost:6379`

> **Caching and queueing. Caches LLM responses so repeated prompts don't hit the model again. Also the job queue for Flowise async steps and the event buffer for Langfuse traces.**

**What it is:** Redis with the RediSearch module (for vector search) and RedisJSON.

**What it does:** Shared by LiteLLM (caching LLM responses to cut costs/latency), Flowise (job queue for async agent steps), and Langfuse (event buffering). Each service has its own ACL user with separate passwords.

**No login UI** — use `redis-cli` or RedisInsight. Admin password is in `agent-infra/docker/.env` as `REDIS_PASSWORD`.

**Why use it vs nothing:** Without Redis, every identical LLM prompt hits the model again. With Redis caching in LiteLLM, repeated prompts are served from cache in milliseconds. Also enables async/queue patterns for long-running agent tasks.

---

### Langfuse — `http://localhost:3002`

> **Observability, not just logs. Shows you the exact prompt that went in, the exact completion that came out, which tools were called, token counts, latency per step, and cost. Logs tell you something happened — Langfuse shows you what happened inside the LLM.**

**What it is:** An open-source LLM observability platform. Think Datadog but for AI agents.

**What it does:** Every LLM call your agent makes gets recorded as a "trace" in Langfuse — the full input messages, the model response, tool calls, token counts, latency, and cost. You can see exactly what your agent said to the LLM, what the LLM replied, which tools it called, and how long each step took.

**Login:** Go to `http://localhost:3002` and sign in with:
- Email: `admin@admin.com`
- Password: `ckwYUI73SJTJU4wBEg8c` (from `agent-infra/docker/.env` → `LANGFUSE_INIT_USER_PASSWORD`)

The project is pre-seeded as **"AI Inference"** under the **"Agentic AI Stack"** org.

**What you see after logging in:**
- **Traces** — one trace per agent run, showing the full message flow
- **Generations** — each individual LLM call within a trace (first call, tool-result call, etc.)
- **Sessions** — groups all traces from one `session_id` together so you can see a full conversation
- **Dashboard** — token usage, latency, cost over time

**Why use it vs just reading logs:** Structured logs tell you something happened. Langfuse tells you *what* happened inside the LLM — the exact prompt, the exact completion, which tool was chosen and why. It's how you debug why your agent said something wrong, catch prompt regressions, and track cost.

---

### Flowise — `http://localhost:3000` (disabled by default)

> **No-code agent builder. Prototypes and workflows that don't need custom Python live here. Anything needing real tool integration, memory control, or custom business logic belongs in `agent-service`. Both share the same LiteLLM backend and both show up in Langfuse.**

**What it is:** A drag-and-drop visual builder for AI workflows — no code required.

**What it does:** Lets non-engineers build and test agent chains using a GUI. Connects to LiteLLM as its LLM backend and Postgres as its storage. Useful for rapid prototyping of new agent flows before they get built properly in `agent-service`.

**Note:** Flowise is in the `flowise` Docker Compose profile and does not start by default. To start it: `docker compose --profile flowise up -d flowise` from `agent-infra/docker/`. On first run you must create an owner account at `http://localhost:3000` before it accepts any traffic (security measure).

**Why use it:** Good for showing non-technical stakeholders what the agent does, or for prototyping a new workflow before writing Python.

---

## agent-infra vs agent-service standalone — when to use which

> **Use standalone (`APP_MODE=local`) when you're writing code and want fast iteration — just Ollama, no Docker needed. Switch to prod (`APP_MODE=prod`) when you want to see what the agent is actually doing, share it with a team, or validate production behavior.**

| | `APP_MODE=local` (standalone) | `APP_MODE=prod` (with agent-infra) |
|---|---|---|
| **LLM backend** | Ollama direct | LiteLLM → Ollama (or any model) |
| **Database** | SQLite file on disk | Postgres (shared, persistent, queryable) |
| **Vector store** | ChromaDB local files | ChromaDB local files (same for now) |
| **Observability** | Structured logs to stdout | Full Langfuse traces in the UI |
| **Auth / rate limiting** | None | LiteLLM keys and budgets |
| **When to use** | Dev on your laptop, quick iteration | Testing production behavior, team shared instance, debugging with traces |
| **Requirements** | Just Ollama | Docker + `make run` |

**The short version:** Use standalone when you're writing code and want fast iteration. Switch to prod mode when you want to see what the agent is actually doing, share it with a team, or validate production behavior.

---

## Downsides

The toolkit solves infrastructure deployment well, but there are real gaps to weigh before adopting it.

- **No evaluation pipeline.** There's no way to measure agent output quality, catch regressions, or benchmark model/prompt changes over time. Langfuse gives you observability into what happened, but nothing here tells you whether the agent's answers are actually *good*.
- **No automated tests or CI.** There's no test suite for `agent-service` or the infra layer, and no CI workflow. Correctness depends entirely on manual verification.
- **Secrets are stored — and documented — in plaintext.** `agent-infra/docker/.env` holds the LiteLLM master key and Postgres/Redis/Flowise/Langfuse/ClickHouse/MinIO passwords in cleartext, with no vault or secrets-manager integration. Several of those values are reproduced directly in this report (LiteLLM master key, `agentdb` password, Langfuse admin credentials). `SECURITY.md` is boilerplate pointing to Intel's vulnerability-reporting page and doesn't address this pattern.
- **High operational overhead relative to the actual "intelligence" delivered.** Running this stack means deploying and monitoring 9+ services (LiteLLM, vLLM/SGLang, Redis, Postgres, Flowise, Langfuse, Agent Sandbox, KubeRay, Prometheus/Grafana/Loki), while the actual agent reasoning lives entirely outside the infra layer — `core/` and `plugins/` are pure Ansible/shell deployment automation, not agent logic.
- **Not cloud-native by default.** The Kubernetes path targets bare-metal Intel Xeon via Kubespray, not EKS/AKS/GKE. Teams on managed cloud Kubernetes need to adapt or replace the provided deployment tooling themselves.
- **Inconsistent vector-store story.** Postgres+pgvector is provisioned specifically for long-term memory and RAG, but per the toolkit's own local-vs-prod comparison above, `agent-service` uses local ChromaDB files in *both* modes — leaving pgvector's actual role unclear.
- **Operational friction in a couple of components.** LiteLLM has no admin UI — key and model management is REST API or YAML-file only. Flowise is disabled by default and requires manually enabling its Docker Compose profile plus a first-run owner-account setup before it accepts traffic.
