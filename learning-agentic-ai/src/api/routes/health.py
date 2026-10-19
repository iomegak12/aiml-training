"""Probe endpoints: /health (liveness) and /ready (readiness)."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.config import APP_NAME, app_version
from api.dependencies import get_runtime
from api.runtime import AgentRuntime
from api.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """Returns `200` with `status: "ok"` while the server process is running.

    It does not check dependencies; use `GET /ready` for that. Not rate limited.
    """
    return HealthResponse(name=APP_NAME, version=app_version())


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    responses={503: {"model": ReadyResponse, "description": "One or more checks failed."}},
)
def ready(runtime: AgentRuntime = Depends(get_runtime)) -> JSONResponse:
    """Reports whether the API can serve chat requests. Local checks only; OpenAI is not called.

    | check | passes when |
    |---|---|
    | `settings` | `OPENAI_MODEL` and `OPENAI_REASONING_EFFORT` are valid |
    | `openai_api_key` | `OPENAI_API_KEY` is set |
    | `database` | the ticket database answers a query |
    | `agents` | the chat and planning agents were built at startup |

    Returns `200` with `status: "ready"` when all pass, otherwise `503` with `status: "not_ready"`.
    Not rate limited.
    """
    checks = runtime.readiness_checks()
    is_ready = all(check["ok"] for check in checks.values())
    body = ReadyResponse(status="ready" if is_ready else "not_ready", checks=checks)
    return JSONResponse(body.model_dump(), status_code=200 if is_ready else 503)
