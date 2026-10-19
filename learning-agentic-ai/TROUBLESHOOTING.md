# Troubleshooting

Start with these two checks; they explain most problems:

```bash
curl http://localhost/api/ready      # Docker (through nginx): which readiness check fails, and why
curl http://localhost:8000/ready     # local run (make run)
tail -n 20 logs/api.log              # recent requests and errors (JSON)
```

In the web app, the bell icon shows the same readiness checks. Every response has an `X-Request-ID` header (shown under **Details** in the chat's error bubbles). Search the log for it to find the matching entry and any error traceback.

---

## Startup

### The banner says `DEGRADED` / `/ready` returns 503

The server starts even when the agent cannot be built. Check the `checks` in `/ready`:

| Failing check | Fix |
|---|---|
| `settings` | Set `OPENAI_MODEL` and a valid `OPENAI_REASONING_EFFORT` in `.env` |
| `openai_api_key` | Set `OPENAI_API_KEY` in `.env` |
| `database` | Check `TICKETS_DB_PATH` and that its folder is writable |
| `agents` | Fix the items above, then **restart** the server (agents are built at startup) |

### `ApiConfigurationError: API_PORT=... must be a number`

`API_PORT` must be an integer from 1 to 65535, and `LOG_LEVEL` one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

### `address already in use` / port 8000 busy

Another process uses the port. Stop it, or set `API_PORT` in `.env`. (In Docker the API port is not published; see the Web app section for port 80.)

### `UnicodeEncodeError` in the console on Windows

Old Windows consoles use a legacy code page. Use Windows Terminal, or set `PYTHONIOENCODING=utf-8` before starting. The banner never stops the server; it logs a warning instead.

## Chat requests

### `503 AGENT_NOT_READY`

See [the banner says DEGRADED](#the-banner-says-degraded--ready-returns-503).

### `502 UPSTREAM_AUTH_ERROR`

OpenAI rejected the API key. Check `OPENAI_API_KEY` (no quotes or spaces) and that the key's project can use `OPENAI_MODEL`.

### `502 UPSTREAM_RATE_LIMITED`

Your OpenAI account hit its own rate limit or quota. Wait, or check usage and billing in the OpenAI dashboard. This is different from the API's own limit (`429 RATE_LIMITED`).

### `502 UPSTREAM_ERROR` mentioning `reasoning.summary` or organization verification

Some OpenAI organisations must be verified before the API returns reasoning summaries. Verify the organisation in the OpenAI dashboard.

### `429 RATE_LIMITED`

More than 100 requests in 60 seconds came from your IP. Wait for `Retry-After` seconds (30). Behind a reverse proxy all clients share the proxy's IP; see the rate-limit notes in the README.

### `409 THREAD_BUSY`

A request on the same `thread_id` is still running. Wait for it to finish, or use a different thread.

### `409 THREAD_MODE_MISMATCH`, `PLAN_PENDING`, `NO_PENDING_PLAN`

- A thread started with `mode: "plan"` stays a plan thread, and a chat thread stays a chat thread.
- While a plan awaits a decision, send `POST /chat/decision` before asking for a new plan.
- `NO_PENDING_PLAN`: the plan was already decided, or the agent answered without needing a plan.

### The agent forgot the conversation

Conversations live in memory and are lost when the server or container restarts. Also check that you send the same `thread_id`.

### Streaming shows everything at once

Use `curl -N` (no buffering). If a reverse proxy sits in front, disable response buffering for `/chat-streaming` (the API sends `X-Accel-Buffering: no` for nginx).

### No `reasoning` events in the stream

Reasoning summaries are optional; the model may not produce one for simple questions.

## Docker

### `make: command not found` (Windows)

Install GNU Make (for example `choco install make`), or run the commands directly: `docker compose up -d --build` and `docker compose down`.

### Container is `unhealthy`

```bash
make logs
```

The health check calls `http://127.0.0.1:8000/health` inside the container. Look for startup errors in the logs.

### `Permission denied` writing `/app/logs` or `/app/data` (Linux hosts)

The container runs as a non-root user (UID 999). Make the bind-mounted folders writable for it:

```bash
mkdir -p data logs && sudo chown -R 999:999 data logs
```

### Logs or tickets missing on the host

Compose mounts `./logs` and `./data` relative to the folder containing `docker-compose.yml`. Run `make start` from the project root.

## Web app

### `http://localhost` doesn't load, or port 80 is in use

Another program (IIS, Skype, another web server) may hold port 80. Stop it, or change the web port mapping in `docker-compose.yml` (for example `"8080:80"`) and open `http://localhost:8080`.

### The page loads but chat shows "The service is starting or unavailable"

nginx answers but the API doesn't. Check `make status`: the `api` container must be `healthy` (the web container only starts after it). Then check `make logs` for API startup errors.

### Streaming replies arrive all at once

The bundled nginx config disables proxy buffering for `/api/`. If you put another proxy or CDN in front, disable response buffering there too for `/api/chat-streaming`.

### The bell shows a badge / "Assistant needs attention"

Click the bell to see which readiness check fails; see [the banner says DEGRADED](#the-banner-says-degraded--ready-returns-503).

### Conversations disappeared

The chat history is kept in memory only and is cleared when you refresh or close the tab. The API also forgets conversations when it restarts.

### "Approve the plan above or request changes to continue"

A plan is waiting for your decision; the input stays locked until you choose **Approve & run** or **Request changes** on the plan card.

### `make web-dev`: API calls fail with 502 / ECONNREFUSED

The Vite dev server proxies `/api` to `http://localhost:8000`. Start the API first with `make run`, or set `VITE_API_PROXY_TARGET` to another API URL.

### Swagger "Try it out" fails behind nginx

Open Swagger through nginx at `http://localhost/api/docs`. It relies on `API_ROOT_PATH=/api`, which Compose sets for the API container.

## Tests

### Tests fail with OpenAI or network errors

They should not: the tests use a scripted fake model and never call OpenAI. Make sure you run them with `make test` from the project root so `tests/helpers.py` is importable.
