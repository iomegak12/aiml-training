"""Chat endpoints: /chat, /chat-streaming and /chat/decision."""

import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from api.dependencies import get_runtime
from api.errors import problem_body, problem_from_exception
from api.runtime import AgentRuntime, ChatOutcome
from api.schemas import ChatRequest, ChatResponse, ChatStreamRequest, DecisionRequest, problem_responses

router = APIRouter(tags=["Chat"])


def _log_outcome(request: Request, message: str | None, outcome: ChatOutcome) -> ChatResponse:
    request.state.log.update(
        {
            "thread_id": outcome.thread_id,
            "mode": outcome.mode,
            "chat_status": outcome.status,
            "user_message": message,
            "reply": outcome.reply,
            "plan": outcome.plan,
        }
    )
    return ChatResponse(**outcome.__dict__)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with the agent",
    responses=problem_responses(409, 422, 429, 502, 503),
)
def chat(body: ChatRequest, request: Request, runtime: AgentRuntime = Depends(get_runtime)) -> ChatResponse:
    """Send a message to the IT support agent and get the complete reply.

    - **Conversation memory:** omit `thread_id` to start a new conversation. The response returns a
      `thread_id`; send it with later messages to continue the same conversation.
    - **`mode: "chat"`** (default): the agent runs the request and `reply` holds its answer.
    - **`mode: "plan"`**: the agent first proposes a plan. The response has `status: "awaiting_approval"`
      and `plan`; nothing is executed until you approve it with `POST /chat/decision`.

    The agent can register, find, get, update, resolve and archive IT support tickets, and use the
    local tools (current location, weather and current time).
    """
    if body.mode == "plan":
        outcome = runtime.plan(body.message, body.thread_id)
    else:
        outcome = runtime.chat(body.message, body.thread_id)
    return _log_outcome(request, body.message, outcome)


@router.post(
    "/chat/decision",
    response_model=ChatResponse,
    summary="Approve or reject a proposed plan",
    responses=problem_responses(404, 409, 422, 429, 502, 503),
)
def decide(body: DecisionRequest, request: Request, runtime: AgentRuntime = Depends(get_runtime)) -> ChatResponse:
    """Approve or reject the plan proposed by `POST /chat` with `mode: "plan"`.

    - **`approve: true`**: the agent executes the plan and the response holds the final `reply`
      (`status: "completed"`).
    - **`approve: false`**: the agent revises the plan using your `feedback` and the response holds
      the revised `plan` (`status: "awaiting_approval"`) for another decision.
    """
    outcome = runtime.decide(body.thread_id, body.approve, body.feedback)
    message = None if body.approve else f"[plan rejected] {body.feedback or ''}".strip()
    return _log_outcome(request, message, outcome)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post(
    "/chat-streaming",
    summary="Chat with the agent (Server-Sent Events)",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "A `text/event-stream` of agent events.",
            "content": {
                "text/event-stream": {
                    "example": (
                        'event: start\ndata: {"thread_id": "3f8e..."}\n\n'
                        'event: tool_call\ndata: {"name": "get_location", "args": {}, "subagent": false}\n\n'
                        'event: token\ndata: {"text": "It is partly", "subagent": false}\n\n'
                        'event: done\ndata: {"thread_id": "3f8e...", "reply": "It is partly cloudy..."}\n\n'
                    )
                }
            },
        },
        **problem_responses(409, 422, 429, 503),
    },
)
def chat_streaming(
    body: ChatStreamRequest, request: Request, runtime: AgentRuntime = Depends(get_runtime)
) -> StreamingResponse:
    """Send a message and receive the agent's work live as **Server-Sent Events**.

    Events (each `data` is JSON):

    | event | data |
    |---|---|
    | `start` | `thread_id` |
    | `reasoning` | `text`: the model's reasoning summary, streamed |
    | `token` | `text`: the answer, streamed |
    | `tool_call` | `id`, `name`, `args` |
    | `tool_result` | `tool_call_id`, `name`, `content` |
    | `done` | `thread_id`, `reply` (the full answer) |
    | `error` | RFC 9457 problem details (the stream then ends) |

    Every event except `start`/`done`/`error` also has `subagent` (true for events from a subagent).
    Use `thread_id` as in `POST /chat` to continue a conversation. Plan mode is only available on `POST /chat`.

    Try it with: `curl -N -X POST http://localhost:8000/chat-streaming -H "Content-Type: application/json"
    -d '{"message": "What time is it in Tokyo?"}'`
    """
    thread_id, events = runtime.stream(body.message, body.thread_id)
    log = request.state.log
    log.update({"thread_id": thread_id, "mode": "chat", "user_message": body.message, "streaming": True})

    def event_stream() -> Iterator[str]:
        reply: list[str] = []
        yield _sse("start", {"thread_id": thread_id})
        try:
            for event in events:
                if event["type"] == "token" and not event["subagent"]:
                    reply.append(event["text"])
                yield _sse(event["type"], {k: v for k, v in event.items() if k != "type"})
            log["reply"] = "".join(reply)
            yield _sse("done", {"thread_id": thread_id, "reply": log["reply"]})
        except Exception as exc:
            status, code, detail, extensions = problem_from_exception(exc)
            log.update({"reply": "".join(reply), "stream_error": code})
            request.app.state.logger.error("Streaming failed [%s]: %s", request.state.request_id, exc, exc_info=exc)
            yield _sse(
                "error",
                problem_body(
                    status, code, detail, instance=request.url.path, request_id=request.state.request_id, **extensions
                ),
            )
        finally:
            events.close()  # releases the thread if the client disconnected

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
