"""Request context middleware: request IDs, JSON access logging and a last-resort error handler.

Implemented as pure ASGI middleware so streaming (SSE) responses are logged when the
body actually finishes, with the full duration and the streamed reply.
"""

import logging
import re
import time
from typing import Any
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.errors import problem_from_exception, problem_response
from api.logging_setup import ACCESS_LOGGER, APP_LOGGER

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestContextMiddleware:
    """Assigns a request ID, logs one JSON line per request and converts unhandled errors to 500 problems.

    Endpoints can add fields to the log entry through `request.state.log` (a dict),
    e.g. thread_id, message and reply.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.access_logger = logging.getLogger(ACCESS_LOGGER)
        self.error_logger = logging.getLogger(APP_LOGGER)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        incoming_id = headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming_id if _VALID_REQUEST_ID.match(incoming_id) else uuid4().hex

        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["log"] = {}

        started = time.perf_counter()
        status: int | None = None
        logged = False

        def write_log() -> None:
            nonlocal logged
            if logged:
                return
            logged = True
            client = scope.get("client")
            fields: dict[str, Any] = {
                "request_id": request_id,
                "client_ip": client[0] if client else None,
                "method": scope["method"],
                "path": scope["path"],
                "query": scope.get("query_string", b"").decode("latin-1") or None,
                "status": status,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "user_agent": headers.get("user-agent"),
                **state.get("log", {}),
            }
            self.access_logger.info("request", extra={"fields": fields})

        async def send_with_context(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                write_log()

        try:
            await self.app(scope, receive, send_with_context)
        except Exception as exc:
            self.error_logger.error("Unhandled error [%s]: %s", request_id, exc, exc_info=exc)
            if status is None:  # nothing sent yet: answer with a 500 problem
                code_status, code, detail, extensions = problem_from_exception(exc)
                response = problem_response(
                    code_status, code, detail, instance=scope["path"], request_id=request_id, **extensions
                )
                await response(scope, receive, send_with_context)
        finally:
            write_log()  # e.g. the client disconnected mid-stream
