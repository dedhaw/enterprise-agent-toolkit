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
agent-service/  ← FastAPI agent service built on top of it
frontend/       ← React chatbot UI for testing
```

`agent-service` is designed to run standalone locally (talking directly to Ollama) and to slot into the full infra platform in production — using LiteLLM as its gateway, Postgres/Redis as its data layer, and Langfuse for tracing.

The infra is the stage. `agent-service` is what performs on it.
