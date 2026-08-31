SRC_DIR := $(shell pwd)
VENV := $(SRC_DIR)/.venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn

.PHONY: install run dev lint clean

## Create venv and install dependencies
install:
	@python3 -m venv $(VENV)
	@$(PIP) install --upgrade pip -q
	@$(PIP) install -r requirements.txt
	@echo "✔  Dependencies installed"

## Run the service (production mode)
run: $(VENV)
	@mkdir -p data
	$(UVICORN) src.app:app --host 0.0.0.0 --port 8000

## Run with auto-reload (development)
dev: $(VENV)
	@mkdir -p data
	$(UVICORN) src.app:app --host 0.0.0.0 --port 8000 --reload

## Remove venv and data
clean:
	@rm -rf $(VENV) data __pycache__ src/__pycache__
	@echo "✔  Cleaned"

$(VENV):
	@$(MAKE) install
