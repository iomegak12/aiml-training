# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-10-16

### Added

- **Corvana Networks web app** (`web/`): React + Vite in JavaScript, styled with CSS Modules, using the Outfit font and a new Corvana Networks logo.
  - **Home** page built from the README, **Support** page with the AI chat assistant, and **Contact Us** page with demo contact details and a `mailto:` form.
  - Chat with **Streaming** and **Plan first** switches. Streaming shows live tool-activity chips, a collapsible reasoning summary, and Markdown answers.
  - **Plan approval cards** with Approve & run and Request changes (with feedback), shown inline. Each card records its decision; revised plans appear as new cards.
  - Animated **thinking indicator** with rotating phase and good-vibe messages.
  - Friendly **error bubbles** per API error code, with a rate-limit countdown, details and Retry.
  - **Service status bell** backed by `/ready`; in-memory conversation history with search.
- **nginx** (web container) serving the app on port 80 and proxying `/api/*` to the API, with SSE passed through unbuffered.
- Web Dockerfile (multistage: `node:22-alpine` build → `nginx:1.28-alpine`) and `web/.dockerignore`.
- `web` service in Docker Compose; Makefile targets `web-install` and `web-dev`.
- API settings `API_ROOT_PATH`, `FORWARDED_ALLOW_IPS` and `PUBLIC_BASE_URL` for running behind a reverse proxy. uvicorn now honours `X-Forwarded-For` from trusted proxies.

### Changed

- In Docker the API is no longer published on port 8000; it is reachable only through nginx at `http://localhost/api`.
- Rate limits and request logs use the real client IP behind nginx instead of the proxy's IP.
- The planning agent now treats a successful `write_todos` call as approval and executes the plan immediately. Previously it could ask for confirmation again after approval.

## [0.1.0] - 2026-10-16

### Added

- **REST API** (FastAPI + uvicorn):
  - `POST /chat` with conversation memory (`thread_id`) and a plan → approve → execute flow (`mode: "plan"`)
  - `POST /chat/decision` to approve or reject a proposed plan
  - `POST /chat-streaming` with Server-Sent Events (`start`, `reasoning`, `token`, `tool_call`, `tool_result`, `done`, `error`)
  - `GET /health` (liveness) and `GET /ready` (local readiness checks)
  - OpenAPI documentation with Swagger UI (`/docs`) and ReDoc (`/redoc`)
- Structured errors as RFC 9457 Problem Details with `code` and `request_id`.
- Per-IP rate limiting: 100 requests per minute, then a 30-second block.
- JSON request logs in a rotating file (10 MB × 5), a coloured one-line console log, and `X-Request-ID` tracing.
- Colourful startup banner with URLs, model, database, log file and rate limit.
- `main.py` entry point, configured through `.env` (`API_HOST`, `API_PORT`, `LOG_DIR`, `LOG_LEVEL`).
- Multistage, non-root Docker image with a health check; Docker Compose with volumes for logs and data.
- Makefile with `start`, `stop`, `run`, `test`, `build`, `logs`, `status`, `install` and `help` targets.
- Project documentation: README, LICENSE (MIT), CONTRIBUTING, TROUBLESHOOTING, SECURITY and CODE_OF_CONDUCT.
- IT support Deep Agent (`ticket_agent`) using OpenAI GPT-5.1 with configurable model and reasoning effort.
- Agent tools (`agent_tools`) for every ticket operation, plus location, weather and time tools.
- IT support ticket library (`it_tickets`) on SQLite with SQLAlchemy and Pydantic v2 validation.
- Notebook walkthrough `notebooks/it-support-agent.ipynb`.

