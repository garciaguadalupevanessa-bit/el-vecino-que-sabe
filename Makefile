# Developer shortcuts. Run `make help` to list them.
# Requires GNU Make (Linux, macOS, WSL, or Git Bash with make installed).
# Without make, run the commands shown in each target by hand.

ifeq ($(OS),Windows_NT)
SHELL := C:/Program Files/Git/bin/sh.exe
.SHELLFLAGS := -c
endif
COMPOSE ?= docker compose
DB_USER ?= elvecino
DB_NAME ?= elvecinoquesabe

.DEFAULT_GOAL := help
.PHONY: help setup doctor doctor-up up up-d down reset logs ps test test-db test-frontend test-all \
        seed probe-llm psql frontend-install frontend-dev plan-dry plan graph

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-17s %s\n", $$1, $$2}'

# ---------- Setup and stack ----------
setup: ## Create .env from .env.example (never overwrites an existing one)
	@if [ -f .env ]; then echo ".env already exists"; else cp .env.example .env && echo "Created .env: now fill in LLM_API_KEY"; fi

doctor: ## Check that your machine is ready (Git, Docker, .env, key, ports)
	@"$(SHELL)" ./scripts/doctor.sh

doctor-up: ## Check the running stack (API, Postgres, frontend, nginx proxy)
	@"$(SHELL)" ./scripts/doctor.sh --up

up: ## Build and start the whole stack in the foreground
	$(COMPOSE) up --build

up-d: ## Build and start the whole stack in the background
	$(COMPOSE) up --build -d

down: ## Stop the stack (keeps the database)
	$(COMPOSE) down

reset: ## Stop the stack and DELETE the database volume
	$(COMPOSE) down -v

logs: ## Follow the logs (all services, or one: make logs SERVICE=backend)
	$(COMPOSE) logs -f --tail=100 $(SERVICE)

ps: ## Show the state of the services
	$(COMPOSE) ps

# ---------- Tests ----------
test: ## Backend tests (data from the JSON files or Postgres, as configured)
	$(COMPOSE) run --rm backend pytest

test-db: ## Postgres integration tests (EMPTIES the aids and blocks tables of the dev database)
	$(COMPOSE) run --rm backend sh -c 'TEST_DATABASE_URL="$$DATABASE_URL" pytest tests/test_db.py -v'

test-frontend: ## Frontend logic tests (needs Node 18+)
	cd frontend && npm test

test-all: test test-frontend ## Backend and frontend tests

# ---------- Data and agent ----------
seed: ## Load backend/data/*.json into Postgres (upsert)
	$(COMPOSE) run --rm backend python -m app.db.seed

probe-llm: ## Check the Groq key, list models and test function calling
	$(COMPOSE) run --rm backend python scripts/probe_groq.py

psql: ## Open a psql shell in the database (stack must be running)
	$(COMPOSE) exec db psql -U $(DB_USER) -d $(DB_NAME)

# ---------- Frontend development ----------
frontend-install: ## Install the frontend dependencies
	cd frontend && npm install

frontend-dev: ## Start Vite with hot reload (run "make up-d" first for the API)
	cd frontend && npm run dev

# ---------- Work plan ----------
plan-dry: ## Show what the plan would create on GitHub (needs REPO=ORG/REPO)
	@test -n "$(REPO)" || { echo "Usage: make plan-dry REPO=ORG/REPO"; exit 1; }
	python plan/create_issues.py --repo $(REPO) --dry-run

plan: ## Create/refresh labels, milestones and issues (REPO=ORG/REPO, optional ARGS="--users P1=a,... --project 1 --owner ORG")
	@test -n "$(REPO)" || { echo "Usage: make plan REPO=ORG/REPO [ARGS=...]"; exit 1; }
	python plan/create_issues.py --repo $(REPO) $(ARGS)

graph: ## Regenerate the dependency graph from plan/tasks.csv
	python plan/build_graph.py
