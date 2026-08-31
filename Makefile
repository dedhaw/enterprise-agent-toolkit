REPO_ROOT := $(shell pwd)
INFRA_DIR := $(REPO_ROOT)/agent-infra
DOCKER_DIR := $(INFRA_DIR)/docker
FRONTEND_DIR := $(REPO_ROOT)/frontend
AGENT_SERVICE_DIR := $(REPO_ROOT)/agent-service
COMPOSE := docker compose -f $(DOCKER_DIR)/docker-compose.yml
LITELLM_KEY := $(shell grep LITELLM_MASTER_KEY $(DOCKER_DIR)/.env 2>/dev/null | cut -d= -f2 | tr -d '"')
MODEL := qwen3:4b

.PHONY: run stop logs frontend

## Start everything: Ollama model, Docker stack, agent-service, and frontend dev server
run: ollama-ready docker-up litellm-ready agent-service-install agent-service-up frontend-install
	@echo ""
	@echo "✔  Stack is up. Starting frontend..."
	@echo "   Chat UI      → http://localhost:5173"
	@echo "   Agent API    → http://localhost:8000/docs"
	@echo "   LiteLLM      → http://localhost:4000"
	@echo "   Langfuse     → http://localhost:3002"
	@echo ""
	cd $(FRONTEND_DIR) && npm run dev

## Pull the Ollama model and ensure the daemon is running
ollama-ready:
	@echo "→ Checking Ollama..."
	@if ! pgrep -x ollama > /dev/null; then \
		echo "  Starting Ollama..."; \
		ollama serve &>/tmp/ollama.log & \
		sleep 3; \
	fi
	@echo "  Pulling $(MODEL) (skipped if already present)..."
	@ollama pull $(MODEL)

## Deploy the Docker stack (idempotent — skips already-running services)
docker-up:
	@echo "→ Starting Docker services..."
	@$(INFRA_DIR)/deploy-agentic-stack.sh --platform=docker

## Wait for LiteLLM to be healthy, then reload config
litellm-ready:
	@echo "→ Waiting for LiteLLM to be healthy..."
	@for i in $$(seq 1 30); do \
		if curl -sf http://localhost:4000/health/liveliness > /dev/null 2>&1; then \
			echo "  LiteLLM is up."; \
			break; \
		fi; \
		echo "  Waiting... ($$i/30)"; \
		sleep 3; \
	done
	@echo "→ Reloading LiteLLM config..."
	@$(COMPOSE) restart litellm
	@sleep 4

## Install agent-service Python deps (skipped if venv exists)
agent-service-install:
	@if [ ! -d "$(AGENT_SERVICE_DIR)/.venv" ]; then \
		echo "→ Installing agent-service dependencies..."; \
		cd $(AGENT_SERVICE_DIR) && make install; \
	fi

## Start agent-service in background (idempotent)
agent-service-up:
	@if ! curl -sf http://localhost:8000/health > /dev/null 2>&1; then \
		echo "→ Starting agent-service..."; \
		cd $(AGENT_SERVICE_DIR) && mkdir -p data && \
		.venv/bin/uvicorn src.app:app --host 0.0.0.0 --port 8000 &>/tmp/agent-service.log & \
		sleep 3; \
		echo "  Agent service up."; \
	else \
		echo "→ Agent service already running."; \
	fi

## Install frontend npm deps (skipped if node_modules exists)
frontend-install:
	@if [ ! -d "$(FRONTEND_DIR)/node_modules" ]; then \
		echo "→ Installing frontend dependencies..."; \
		cd $(FRONTEND_DIR) && npm install; \
	fi

## Stop all Docker services, agent-service, and Ollama
stop:
	@echo "→ Stopping agent-service..."
	@pkill -f "uvicorn src.app:app" 2>/dev/null || true
	@echo "→ Stopping Docker services..."
	@$(INFRA_DIR)/deploy-agentic-stack.sh --platform=docker --down
	@echo "→ Stopping Ollama..."
	@pkill ollama 2>/dev/null || true

## Tail logs from all core services
logs:
	@$(COMPOSE) logs -f litellm postgres redis
