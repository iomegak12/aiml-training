# IT Support Agent API - common tasks.
# Requires GNU Make, uv and Docker (with Compose v2).

COMPOSE := docker compose

.DEFAULT_GOAL := help
.PHONY: help install run test build start stop logs status web-install web-dev

help: ## Show available targets
	@echo Targets:
	@echo   make install  - install dependencies with uv
	@echo   make run      - run the API locally with uv
	@echo   make test     - run the test suite
	@echo   make build    - build the Docker images: api and web
	@echo   make start    - build and start api + web in Docker, detached: http://localhost
	@echo   make stop     - stop and remove the Docker containers
	@echo   make logs     - follow the container logs
	@echo   make status   - show container status and health
	@echo   make web-install - install the web app dependencies with npm
	@echo   make web-dev  - run the web app dev server: http://localhost:5173, API on :8000

install: ## Install dependencies
	uv sync

run: ## Run the API locally
	uv run python main.py

test: ## Run the tests
	uv run pytest -q

build: ## Build the Docker images
	$(COMPOSE) build

start: ## Build and start the api and web containers
	$(COMPOSE) up -d --build

stop: ## Stop and remove the containers
	$(COMPOSE) down

logs: ## Follow container logs
	$(COMPOSE) logs -f

status: ## Show container status
	$(COMPOSE) ps

web-install: ## Install web dependencies
	cd web && npm ci

web-dev: ## Run the Vite dev server (proxies /api to http://localhost:8000)
	cd web && npm run dev
