# IT Support Agent API · Corvana Networks

A REST API and web app for an **IT support agent** built with [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/quickstart) and an OpenAI reasoning model (GPT-5.1, high reasoning effort). The agent manages IT support tickets stored in SQLite and has a few local tools (location, weather, current time).

- **FastAPI + uvicorn**, with OpenAPI docs (Swagger UI and ReDoc)
- **`POST /chat`**: complete replies, conversation memory, and an optional **plan → approve → execute** flow
- **`POST /chat-streaming`**: the agent's reasoning, tool calls and answer, live, as Server-Sent Events
- **`GET /health`** and **`GET /ready`** probes
- **Structured errors** (RFC 9457 Problem Details), **per-IP rate limiting**, **JSON request logs**
- **Docker** (multistage, non-root) and **Docker Compose** with volumes for logs and data
- **Corvana Networks web app** (React + Vite) served by **nginx** on port 80, which also proxies every API call

---

## Contents

- [Architecture](#architecture)
- [Requirements](#requirements)
- [Quick start (local)](#quick-start-local)
- [Quick start (Docker)](#quick-start-docker)
- [Web app](#web-app)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Errors](#errors)
- [Rate limiting](#rate-limiting)
- [Logging](#logging)
- [Development](#development)
- [Project structure](#project-structure)
- [More documentation](#more-documentation)

---

## Architecture

```
Browser ──► nginx (web container, port 80)
              ├── /          React app (Home, Support, Contact Us)
              └── /api/*  ─► API container (port 8000, not published)
                               │
                               ▼
RequestContextMiddleware   request ID, JSON access log, last-resort 500 handler
RateLimitMiddleware        100 requests / 60 s per IP, then a 30 s block
   │
   ▼
FastAPI routes (src/api/routes)  ──►  AgentRuntime (src/api/runtime.py)
                                        threads, plan approval, streaming
                                              │
                                              ▼
                               ticket_agent: Deep Agent + GPT-5.1
                                              │
                               agent_tools: ticket tools + local tools
                                              │
                               it_tickets: SQLite via SQLAlchemy ORM
```

| Package | Responsibility |
|---|---|
| `src/it_tickets` | IT ticket library: SQLite + SQLAlchemy + Pydantic v2 validation |
| `src/agent_tools` | LangChain tools wrapping `it_tickets`, plus local tools (dummy weather/location, real time) |
| `src/ticket_agent` | `.env` settings, OpenAI model, Deep Agent builders, streaming, plan approval |
| `src/api` | FastAPI application: routes, runtime, middleware, errors, logging, banner |
| `main.py` | Starts the server with uvicorn |
| `web/` | Corvana Networks web app (React + Vite), nginx config and Dockerfile |
| `notebooks/it-support-agent.ipynb` | Interactive walkthrough of the agent |

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- An OpenAI API key with access to the configured model
- Optional: Docker with Compose v2, and GNU Make
- For web development: Node.js 22.12 or later

## Quick start (local)

```bash
uv sync                     # install dependencies
cp .env.example .env        # then set OPENAI_API_KEY in .env
uv run python main.py       # or: make run
```

On startup the console shows a banner with the URLs, model, database, log file and rate limit. Open:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

## Quick start (Docker)

```bash
cp .env.example .env        # set OPENAI_API_KEY
make start                  # docker compose up -d --build (api + web)
make logs                   # follow logs (banner + requests)
make status                 # container status and health
make stop                   # docker compose down
```

Then open:

- Web app: <http://localhost>
- Swagger UI: <http://localhost/api/docs> · ReDoc: <http://localhost/api/redoc>
- Health / readiness: <http://localhost/api/health> · <http://localhost/api/ready>

Compose runs two services:

| Service | Image | Exposed | Notes |
|---|---|---|---|
| `web` | nginx 1.28 (alpine) + React build | **port 80** | Serves the app; proxies `/api/*` to `api` (prefix stripped, SSE unbuffered) |
| `api` | python 3.12-slim, non-root | not published | Reachable only through nginx; `./data` and `./logs` mounted as volumes |

The API runs with `API_ROOT_PATH=/api` (so Swagger works behind the proxy) and trusts `X-Forwarded-For` from nginx (`FORWARDED_ALLOW_IPS=*`, safe because the API isn't published), so rate limits and logs use the real client IP.

## Web app

**Corvana Networks** is a React + Vite web app (`web/`) that demonstrates the API. In Docker, nginx serves it on port 80 and proxies all API calls (`/api/*`), so the browser only ever talks to nginx.

| Page | What it shows |
|---|---|
| **Home** | What the assistant does, how it works, its tools, the ticket lifecycle and the API endpoints |
| **Support** | The AI Support chat: history sidebar (search, New Chat) and the chat window |
| **Contact Us** | Contact details (demo placeholders) and a form that opens your email app (`mailto:`) |

Support chat features:

- **Streaming / Plan first switches** in the chat header. Streaming shows live tool-activity chips ("Using get_weather…" → done), a collapsible **Reasoning** section and the answer as it's written. Plan first disables streaming (plan mode uses standard responses).
- **Plan approval**: the plan appears as a card with numbered steps. **Approve & run** executes it; **Request changes** sends your feedback and a revised plan appears as a new card. The input is locked while a plan awaits a decision, and every card records the decision and time.
- **Thinking animation**: a gradient orb with rotating phase messages (thinking, planning, executing, revising) and a few good-vibe lines, plus an elapsed-time counter.
- **Friendly errors** per API error code. Rate limiting shows a live countdown and disables Send; every error has collapsible details (code, request ID) and **Retry**.
- **Service status bell** polls `/api/ready` every 30 seconds; click it to see each readiness check.
- **Markdown** replies (lists, tables, code) via `react-markdown` + GFM; raw HTML isn't rendered.
- Conversations are kept **in memory only**: they survive page navigation, not a refresh. Plan-mode and regular turns use separate agent threads, so they don't share memory.

### Developing the web app

```bash
make run            # terminal 1: API on http://localhost:8000
make web-install    # once
make web-dev        # terminal 2: Vite on http://localhost:5173 (proxies /api -> :8000)
```

Code layout (`web/src`): `pages/` (Home, Support, Contact), `components/` (`layout`, `chat`, `common`, `home`), `hooks/` (`useChat` orchestrates standard, streaming and plan requests), `services/` (API client, SSE streaming, status), `context/` (in-memory sessions), `content/` (page copy, prompts, thinking messages) and `styles/` (design tokens). Styling uses CSS Modules and the Outfit font (bundled via `@fontsource`).

## Configuration

All settings are read from `.env` (or the environment).

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | (required) | OpenAI API key. Never logged or displayed. |
| `OPENAI_MODEL` | (required) | Model name, e.g. `gpt-5.1` |
| `OPENAI_REASONING_EFFORT` | (required) | `none`, `minimal`, `low`, `medium`, `high` or `xhigh` (model dependent) |
| `TICKETS_DB_PATH` | (required) | SQLite database file, e.g. `./data/tickets.db` |
| `API_HOST` | `0.0.0.0` | Interface to bind |
| `API_PORT` | `8000` | Port for local runs (in Docker the API is not published; use nginx on port 80) |
| `LOG_DIR` | `./logs` | Directory for `api.log` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` |
| `API_ROOT_PATH` | (empty) | Path prefix when served behind a proxy, e.g. `/api` (set by Compose) |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Proxies trusted for `X-Forwarded-For` (Compose: `*`) |
| `PUBLIC_BASE_URL` | (empty) | Public API URL shown in the banner, e.g. `http://localhost/api` |

If the OpenAI settings or key are missing, the server **still starts**. The banner shows `DEGRADED`, `/ready` returns `503` with the reason, and chat endpoints return `503 AGENT_NOT_READY`. Fix `.env` and restart.

## API reference

The complete, interactive reference is at `/docs`. The examples below call a local server (`http://localhost:8000`); with Docker, use `http://localhost/api` instead. Every request and response can carry an `X-Request-ID` header: send your own, or read the one the server generated.

| Method | Path | Description | Rate limited |
|---|---|---|---|
| `POST` | `/chat` | Send a message; get the complete reply (or a plan in plan mode) | yes |
| `POST` | `/chat-streaming` | Send a message; receive Server-Sent Events | yes |
| `POST` | `/chat/decision` | Approve or reject a proposed plan | yes |
| `GET` | `/health` | Liveness: the process is up | no |
| `GET` | `/ready` | Readiness: settings, API key, database, agents | no |

### Chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Raise a High priority ticket: the 3rd floor printer is jammed. I am Priya from Finance."}'
```

```json
{
  "thread_id": "3f8e2c1a-6b1d-4c1e-9d3f-2a7b5c9e0f11",
  "mode": "chat",
  "status": "completed",
  "reply": "I've registered ticket TKT-00007 ...",
  "plan": null
}
```

To continue the conversation, send the returned `thread_id`:

```bash
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message": "Move it to In Progress", "thread_id": "3f8e2c1a-6b1d-4c1e-9d3f-2a7b5c9e0f11"}'
```

Conversations are kept **in memory** and are lost when the server restarts. A thread handles one request at a time; a concurrent request on the same thread gets `409 THREAD_BUSY`.

### Streaming (Server-Sent Events)

```bash
curl -N -X POST http://localhost:8000/chat-streaming \
  -H "Content-Type: application/json" \
  -d '{"message": "What time is it in Tokyo?"}'
```

```
event: start
data: {"thread_id": "a457e560-..."}

event: tool_call
data: {"id": "call_0X9o...", "name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "subagent": false}

event: tool_result
data: {"tool_call_id": "call_0X9o...", "name": "get_current_time", "content": "{...}", "subagent": false}

event: token
data: {"text": "In Tokyo right now it is", "subagent": false}

event: done
data: {"thread_id": "a457e560-...", "reply": "In Tokyo right now it is Friday, 16 October 2026, 8:35 PM (JST)."}
```

| Event | Data |
|---|---|
| `start` | `thread_id` |
| `reasoning` | `text`: the model's reasoning summary, streamed (when the model provides one) |
| `token` | `text`: the answer, streamed |
| `tool_call` | `id`, `name`, `args` |
| `tool_result` | `tool_call_id`, `name`, `content` |
| `done` | `thread_id`, `reply` |
| `error` | Problem Details (see [Errors](#errors)); the stream then ends |

### Plan → approve → execute

Send `"mode": "plan"` to `/chat`. The agent proposes a plan and **does nothing** until you decide.

```bash
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message": "Check the weather where I am and raise a ticket for facilities", "mode": "plan"}'
```

```json
{
  "thread_id": "9b1c...",
  "mode": "plan",
  "status": "awaiting_approval",
  "reply": null,
  "plan": [
    {"content": "Get the user's location", "status": "in_progress"},
    {"content": "Check the weather there", "status": "pending"},
    {"content": "Register a ticket for Facilities", "status": "pending"}
  ]
}
```

Then approve it, or reject it with feedback:

```bash
# reject: the response contains a revised plan (status awaiting_approval)
curl -X POST http://localhost:8000/chat/decision -H "Content-Type: application/json" \
  -d '{"thread_id": "9b1c...", "approve": false, "feedback": "Use Medium priority"}'

# approve: the agent executes and the response contains the reply (status completed)
curl -X POST http://localhost:8000/chat/decision -H "Content-Type: application/json" \
  -d '{"thread_id": "9b1c...", "approve": true}'
```

After a plan is approved, the agent's progress updates to its plan are approved automatically. Plan mode is available on `/chat` only, not on `/chat-streaming`.

### Readiness

```json
{
  "status": "ready",
  "checks": {
    "settings": {"ok": true, "detail": "openai:gpt-5.1 (effort: high)"},
    "openai_api_key": {"ok": true, "detail": "set"},
    "database": {"ok": true, "detail": "reachable"},
    "agents": {"ok": true, "detail": "chat and planning agents built"}
  }
}
```

`/ready` performs local checks only; it does not call OpenAI.

## Errors

Every error is an [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) `application/problem+json` body:

```json
{
  "type": "about:blank",
  "title": "Too Many Requests",
  "status": 429,
  "detail": "Rate limit of 100 requests per 60s exceeded. Retry after 30s.",
  "instance": "/chat",
  "code": "RATE_LIMITED",
  "request_id": "6c94c96ab8d544389f93cd9545ed1be0",
  "retry_after": 30
}
```

| Status | `code` | When |
|---|---|---|
| 404 | `THREAD_NOT_FOUND`, `NOT_FOUND` | Unknown thread in `/chat/decision`; unknown route |
| 405 | `METHOD_NOT_ALLOWED` | Wrong HTTP method |
| 409 | `THREAD_BUSY` | The thread is already processing a request |
| 409 | `THREAD_MODE_MISMATCH` | A chat thread was used in plan mode, or the other way round |
| 409 | `PLAN_PENDING` | New plan request while a plan awaits a decision |
| 409 | `NO_PENDING_PLAN` | Decision sent but no plan is waiting |
| 422 | `VALIDATION_ERROR` | Invalid body; see `errors` |
| 429 | `RATE_LIMITED` | Rate limit exceeded; see `Retry-After` |
| 500 | `INTERNAL_ERROR` | Unexpected error (details only in the server log, by `request_id`) |
| 502 | `UPSTREAM_AUTH_ERROR`, `UPSTREAM_RATE_LIMITED`, `UPSTREAM_ERROR`, `UPSTREAM_UNAVAILABLE` | OpenAI API problems |
| 503 | `AGENT_NOT_READY` | Agent not configured (see `/ready`) |

Ticket problems (for example "ticket not found" or "cannot update a resolved ticket") are **not** HTTP errors: the tools return them to the agent, which explains them in its reply.

## Rate limiting

- **100 requests per 60-second window per client IP.**
- The request that goes over the limit gets `429`, and the IP is **blocked for 30 seconds**. After the block its counter starts again from zero.
- `/health`, `/ready`, `/docs`, `/redoc` and `/openapi.json` are never limited.
- Responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` (seconds); a `429` also has `Retry-After`.
- The client IP is the direct peer address, or the `X-Forwarded-For` client when the request comes from a trusted proxy (`FORWARDED_ALLOW_IPS`). In Docker, nginx is trusted, so each browser has its own limit.
- The limits are kept in process memory, so each server process limits independently.

## Logging

Every request produces **one JSON line** in `logs/api.log` (rotated at 10 MB, 5 backups):

```json
{"timestamp": "2026-10-16T11:35:13.620+00:00", "level": "INFO", "logger": "api.access",
 "request_id": "31d0f044...", "client_ip": "127.0.0.1", "method": "POST", "path": "/chat-streaming",
 "query": null, "status": 200, "duration_ms": 4802.3, "user_agent": "curl/8.15.0",
 "thread_id": "a457e560-...", "mode": "chat", "user_message": "What time is it in Tokyo?",
 "streaming": true, "reply": "In Tokyo right now it is ...", "message": "request"}
```

Chat requests also include `thread_id`, `mode`, `user_message` and `reply` (and `plan` in plan mode). **The log file therefore contains conversation text**; protect it accordingly (see [SECURITY.md](SECURITY.md)). Errors are logged with their traceback.

The console shows a minimal coloured line per request, without message text:

```
17:04:27 POST   /chat 200 3600ms 127.0.0.1 [6c94c96a]
```

## Development

```bash
make install      # uv sync
make test         # uv run pytest -q
make run          # run locally
```

The tests need **no OpenAI access**: a scripted fake chat model drives the real Deep Agent, so the tests cover tools, streaming, plan approval, rate limiting, logging and error handling. See [CONTRIBUTING.md](CONTRIBUTING.md).

| Make target | Command |
|---|---|
| `help` | List targets |
| `install` | `uv sync` |
| `run` | `uv run python main.py` |
| `test` | `uv run pytest -q` |
| `build` | `docker compose build` |
| `start` | `docker compose up -d --build` (api + web) |
| `stop` | `docker compose down` |
| `logs` | `docker compose logs -f` |
| `status` | `docker compose ps` |
| `web-install` | `cd web && npm ci` |
| `web-dev` | `cd web && npm run dev` (Vite on <http://localhost:5173>, proxies `/api` to `http://localhost:8000`) |

## Project structure

```
.
├── main.py                    # server entry point (uvicorn)
├── src/
│   ├── api/                   # FastAPI app
│   │   ├── app.py             # create_app() factory + lifespan
│   │   ├── routes/            # chat.py, health.py
│   │   ├── runtime.py         # AgentRuntime (threads, plans, streaming)
│   │   ├── schemas.py         # request/response models
│   │   ├── errors.py          # Problem Details handlers
│   │   ├── middleware.py      # request ID + access log
│   │   ├── rate_limit.py      # per-IP limiter
│   │   ├── logging_setup.py   # JSON file + console logging
│   │   ├── banner.py          # startup banner
│   │   └── config.py          # API settings
│   ├── ticket_agent/          # Deep Agent, model, streaming, plan approval
│   ├── agent_tools/           # ticket tools + local tools
│   └── it_tickets/            # ticket library (SQLite / SQLAlchemy / Pydantic)
├── tests/                     # pytest suite (tests/api for the API)
├── notebooks/                 # it-support-agent.ipynb walkthrough
├── web/                       # Corvana Networks web app (React + Vite + nginx)
├── Dockerfile, docker-compose.yml, Makefile
└── .env.example
```

## More documentation

- [CONTRIBUTING.md](CONTRIBUTING.md): how to set up, test and submit changes
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md): common problems and fixes
- [CHANGELOG.md](CHANGELOG.md): release history
- [SECURITY.md](SECURITY.md): reporting vulnerabilities and deployment guidance
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md): community standards

## License

[MIT](LICENSE) © 2026 Ramkumar
