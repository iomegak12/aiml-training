"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from api.banner import print_banner
from api.config import APP_NAME, ApiSettings, app_version
from api.errors import register_exception_handlers
from api.logging_setup import APP_LOGGER, setup_logging
from api.middleware import RequestContextMiddleware
from api.rate_limit import RateLimiter, RateLimitMiddleware
from api.routes import chat, health
from api.runtime import AgentRuntime

DESCRIPTION = """
REST API for the **IT Support Deep Agent**: a LangChain Deep Agents agent (OpenAI reasoning model)
that manages IT support tickets and has local tools for location, weather and time.

* **Chat**: `POST /chat` (complete reply, optional plan → approve → execute flow) and
  `POST /chat-streaming` (Server-Sent Events).
* **Conversations**: send the returned `thread_id` to continue a conversation (kept in memory).
* **Errors**: every error is an RFC 9457 `application/problem+json` body with `code` and `request_id`.
* **Rate limit**: 100 requests/minute per client IP; exceeding it blocks the IP for 30 seconds
  (`/health`, `/ready` and the docs are exempt). See the `X-RateLimit-*` and `Retry-After` headers.
* **Tracing**: send or read `X-Request-ID`; it is included in every log line and error.
"""

OPENAPI_TAGS = [
    {"name": "Chat", "description": "Talk to the IT support agent."},
    {"name": "Health", "description": "Liveness and readiness probes."},
]


def create_app(
    settings: ApiSettings | None = None,
    runtime: AgentRuntime | None = None,
    rate_limiter: RateLimiter | None = None,
    show_banner: bool = True,
) -> FastAPI:
    """Build the FastAPI app.

    Args:
        settings: Server settings; defaults to ApiSettings.from_env().
        runtime: Agent runtime; defaults to AgentRuntime.from_env(), built at startup.
        rate_limiter: Defaults to 100 requests / 60s per IP with a 30s block.
        show_banner: Print the startup banner.
    """
    settings = settings or ApiSettings.from_env()
    setup_logging(settings.log_dir, settings.log_level)
    logger = logging.getLogger(APP_LOGGER)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.runtime = runtime or await run_in_threadpool(AgentRuntime.from_env)
        if show_banner:
            try:
                print_banner(settings, app.state.runtime.info())
            except Exception as exc:  # a cosmetic banner must never stop the server
                logger.warning("Could not print the startup banner: %s", exc)
        logger.info("Server started (agent %s)", "ready" if app.state.runtime.is_ready else "NOT ready")
        yield
        logger.info("Server stopped")

    app = FastAPI(
        title=APP_NAME,
        version=app_version(),
        description=DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        root_path=settings.root_path,  # e.g. "/api" behind nginx, so /docs loads the right openapi.json
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.logger = logger

    register_exception_handlers(app)
    app.include_router(chat.router)
    app.include_router(health.router)

    # Added last = outermost: request context wraps the rate limiter, so 429s are logged too.
    app.add_middleware(RateLimitMiddleware, limiter=rate_limiter or RateLimiter())
    app.add_middleware(RequestContextMiddleware)
    return app
