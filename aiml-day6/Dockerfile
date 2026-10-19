# syntax=docker/dockerfile:1.7
# CRM & Support MCP server - slim multi-stage image.
#   Build:  docker compose build crm-mcp      (or: make mcp-server-up)
#   Stage 1 installs ONLY the server dependency group (fastmcp-slim[server]) from uv.lock,
#           without precompiled .pyc files (smaller image; PYTHONDONTWRITEBYTECODE at runtime).
#   Stage 2 is python:3.12-slim with the virtualenv and the server code, running as non-root.
#   No HEALTHCHECK by design; use `make mcp-server-status` (GET /health) from the host.

# ---------- builder ----------
FROM ghcr.io/astral-sh/uv:0.9.16-python3.12-trixie-slim AS builder
ENV UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --only-group crm-mcp --no-install-project --no-editable

# ---------- runtime ----------
FROM python:3.12-slim-trixie AS runtime
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8765 \
    MCP_PATH=/mcp \
    CRM_DB_PATH=/app/data/crm_support.db
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app \
    && mkdir -p /app/data \
    && chown app:app /app/data
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app src/mcp_servers /app/src/mcp_servers
USER app
EXPOSE 8765
CMD ["python", "-m", "mcp_servers.crm_support"]
