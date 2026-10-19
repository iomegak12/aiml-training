"""Request and response models (also the OpenAPI schema)."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ThreadId = Field(
    default=None,
    pattern=r"^[A-Za-z0-9_-]{1,64}$",
    description="Conversation ID. Omit to start a new conversation; send the returned value to continue it.",
    examples=["3f8e2c1a-6b1d-4c1e-9d3f-2a7b5c9e0f11"],
)


class _Request(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ChatRequest(_Request):
    message: str = Field(
        min_length=1,
        max_length=8000,
        description="The user's message to the agent.",
        examples=["Raise a High priority ticket: the 3rd floor printer is jammed. I'm Priya from Finance."],
    )
    thread_id: str | None = ThreadId
    mode: Literal["chat", "plan"] = Field(
        default="chat",
        description=(
            "`chat` runs the request directly. `plan` makes the agent propose a step-by-step plan first; "
            "the response has status `awaiting_approval` and the plan, to approve or reject via `POST /chat/decision`."
        ),
    )


class ChatStreamRequest(_Request):
    message: str = Field(
        min_length=1,
        max_length=8000,
        description="The user's message to the agent.",
        examples=["What's the weather where I am?"],
    )
    thread_id: str | None = ThreadId


class DecisionRequest(_Request):
    thread_id: str = Field(
        pattern=r"^[A-Za-z0-9_-]{1,64}$",
        description="The plan-mode thread with a plan awaiting approval.",
    )
    approve: bool = Field(description="`true` executes the plan; `false` asks the agent to revise it.")
    feedback: str | None = Field(
        default=None,
        max_length=2000,
        description="Why the plan was rejected / what to change (used when `approve` is false).",
        examples=["Check my location before the weather."],
    )


class PlanStep(BaseModel):
    content: str = Field(description="What the agent will do in this step.")
    status: str = Field(description="pending, in_progress or completed.")


class ChatResponse(BaseModel):
    thread_id: str = Field(description="Conversation ID; send it again to continue the conversation.")
    mode: Literal["chat", "plan"]
    status: Literal["completed", "awaiting_approval"] = Field(
        description="`completed`: `reply` holds the answer. `awaiting_approval`: `plan` holds the proposed steps."
    )
    reply: str | None = Field(default=None, description="The agent's answer (when completed).")
    plan: list[PlanStep] | None = Field(default=None, description="The proposed plan (when awaiting approval).")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    name: str
    version: str


class ReadinessCheck(BaseModel):
    ok: bool
    detail: str


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, ReadinessCheck]


class Problem(BaseModel):
    """RFC 9457 Problem Details."""

    type: str = Field(default="about:blank")
    title: str = Field(examples=["Too Many Requests"])
    status: int = Field(examples=[429])
    detail: str
    instance: str | None = Field(default=None, examples=["/chat"])
    code: str = Field(description="Stable machine-readable error code.", examples=["RATE_LIMITED"])
    request_id: str | None = Field(default=None, description="Matches the X-Request-ID header and the logs.")
    errors: list[dict[str, Any]] | None = Field(default=None, description="Validation errors (422 only).")


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses` entries for the given error statuses."""
    descriptions = {
        404: "Thread not found.",
        409: "Thread conflict (busy, wrong mode, or plan state).",
        422: "Invalid request body.",
        429: "Rate limit exceeded (100 requests/minute per IP, then a 30 second block).",
        500: "Unexpected server error.",
        502: "OpenAI API error.",
        503: "Agent not available (configuration).",
    }
    return {
        status: {
            "model": Problem,
            "description": descriptions[status],
            "content": {"application/problem+json": {}},
        }
        for status in statuses
    }
