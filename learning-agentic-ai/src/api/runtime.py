"""AgentRuntime: owns the agents and conversation threads used by the API."""

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.types import Command

from it_tickets import TicketService
from it_tickets.config import get_database_path
from ticket_agent import (
    AgentSettings,
    build_agent,
    build_planning_agent,
    is_api_key_set,
    iter_agent_events,
)
from api.errors import ApiError

logger = logging.getLogger("api")

Mode = Literal["chat", "plan"]


@dataclass
class _ThreadState:
    mode: Mode
    lock: threading.Lock = field(default_factory=threading.Lock)
    plan_approved: bool = False


@dataclass
class ChatOutcome:
    thread_id: str
    mode: Mode
    status: Literal["completed", "awaiting_approval"]
    reply: str | None = None
    plan: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class RuntimeInfo:
    """Non-secret details shown in the startup banner."""

    model: str | None
    reasoning_effort: str | None
    api_key_set: bool
    database_path: str | None
    error: str | None


class ThreadStream:
    """Iterator over agent events that releases its thread exactly once: when exhausted,
    on error, on close(), or when garbage-collected (e.g. the client disconnected early)."""

    def __init__(self, events: Iterator[dict[str, Any]], release: Callable[[], None]) -> None:
        self._events = events
        self._release: Callable[[], None] | None = release

    def __iter__(self) -> "ThreadStream":
        return self

    def __next__(self) -> dict[str, Any]:
        try:
            return next(self._events)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self._release is not None:
            release, self._release = self._release, None
            try:
                close = getattr(self._events, "close", None)
                if close:
                    close()
            finally:
                release()

    def __del__(self) -> None:
        self.close()


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _user_input(message: str) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": message}]}


def _last_reply(state_values: dict[str, Any]) -> str:
    for message in reversed(state_values.get("messages", [])):
        if isinstance(message, AIMessage) and not message.tool_calls:
            return message.text
    return ""


class AgentRuntime:
    """Runs chat, streaming chat and plan-approval conversations.

    Each thread_id belongs to one mode ("chat" or "plan") and handles one request at a time.
    If the agents could not be built (e.g. OPENAI_API_KEY missing), the runtime still exists
    so the server can start; agent calls then fail with 503 and /ready reports why.
    """

    def __init__(
        self,
        agent: Any | None,
        planner: Any | None,
        ticket_service: TicketService | None,
        settings: AgentSettings | None = None,
        error: str | None = None,
    ) -> None:
        self.agent = agent
        self.planner = planner
        self.ticket_service = ticket_service
        self.settings = settings
        self.error = error
        self._threads: dict[str, _ThreadState] = {}
        self._threads_lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "AgentRuntime":
        """Build the agents from .env settings; never raises."""
        settings = service = None
        try:
            settings = AgentSettings.from_env()
            service = TicketService()
            agent = build_agent(settings=settings, ticket_service=service)
            planner = build_planning_agent(settings=settings, ticket_service=service)
        except Exception as exc:
            logger.warning("Agents not available: %s", exc)
            return cls(None, None, service, settings, error=str(exc))
        return cls(agent, planner, service, settings)

    # --- status ----------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self.agent is not None and self.planner is not None

    def info(self) -> RuntimeInfo:
        try:
            database_path = get_database_path()
        except Exception:
            database_path = None
        return RuntimeInfo(
            model=self.settings.model_id if self.settings else None,
            reasoning_effort=self.settings.reasoning_effort if self.settings else None,
            api_key_set=is_api_key_set(),
            database_path=database_path,
            error=self.error,
        )

    def readiness_checks(self) -> dict[str, dict[str, Any]]:
        """Local readiness checks (no OpenAI call)."""
        checks: dict[str, dict[str, Any]] = {}

        try:
            settings = AgentSettings.from_env()
            checks["settings"] = {"ok": True, "detail": f"{settings.model_id} (effort: {settings.reasoning_effort})"}
        except Exception as exc:
            checks["settings"] = {"ok": False, "detail": str(exc)}

        api_key = is_api_key_set()
        checks["openai_api_key"] = {"ok": api_key, "detail": "set" if api_key else "OPENAI_API_KEY is not set"}

        if self.ticket_service is None:
            checks["database"] = {"ok": False, "detail": "Ticket service not initialised"}
        else:
            try:
                self.ticket_service.find_tickets(title="__readiness_check__")  # cheap ORM query
                checks["database"] = {"ok": True, "detail": "reachable"}
            except Exception as exc:
                checks["database"] = {"ok": False, "detail": str(exc)}

        checks["agents"] = (
            {"ok": True, "detail": "chat and planning agents built"}
            if self.is_ready
            else {"ok": False, "detail": f"Not built: {self.error}. Fix the configuration and restart."}
        )
        return checks

    # --- threads ---------------------------------------------------------------

    def _require_agents(self) -> None:
        if not self.is_ready:
            raise ApiError(503, "AGENT_NOT_READY", f"The agent is not available: {self.error}")

    def _thread(self, thread_id: str | None, mode: Mode, *, create: bool = True) -> tuple[str, _ThreadState]:
        thread_id = thread_id or str(uuid4())
        with self._threads_lock:
            state = self._threads.get(thread_id)
            if state is None:
                if not create:
                    raise ApiError(404, "THREAD_NOT_FOUND", f"Thread '{thread_id}' does not exist.")
                state = self._threads[thread_id] = _ThreadState(mode=mode)
            elif state.mode != mode:
                raise ApiError(
                    409,
                    "THREAD_MODE_MISMATCH",
                    f"Thread '{thread_id}' is a '{state.mode}' thread and cannot be used in '{mode}' mode.",
                )
        return thread_id, state

    @staticmethod
    def _acquire(thread_id: str, state: _ThreadState) -> None:
        if not state.lock.acquire(blocking=False):
            raise ApiError(409, "THREAD_BUSY", f"Thread '{thread_id}' is already processing a request.")

    @contextmanager
    def _busy(self, thread_id: str, state: _ThreadState) -> Iterator[None]:
        self._acquire(thread_id, state)
        try:
            yield
        finally:
            state.lock.release()

    # --- chat ------------------------------------------------------------------

    def chat(self, message: str, thread_id: str | None = None) -> ChatOutcome:
        self._require_agents()
        thread_id, state = self._thread(thread_id, "chat")
        with self._busy(thread_id, state):
            result = self.agent.invoke(_user_input(message), config=_config(thread_id))
        return ChatOutcome(thread_id, "chat", "completed", reply=_last_reply(result))

    def stream(self, message: str, thread_id: str | None = None) -> tuple[str, "ThreadStream"]:
        """Start a streaming chat turn. The thread is reserved until the stream is exhausted or closed."""
        self._require_agents()
        thread_id, state = self._thread(thread_id, "chat")
        self._acquire(thread_id, state)
        events = iter_agent_events(self.agent, message, _config(thread_id))
        return thread_id, ThreadStream(events, state.lock.release)

    # --- plan -> approve -> execute ------------------------------------------------

    def plan(self, message: str, thread_id: str | None = None) -> ChatOutcome:
        self._require_agents()
        thread_id, state = self._thread(thread_id, "plan")
        with self._busy(thread_id, state):
            config = _config(thread_id)
            if self.planner.get_state(config).interrupts:
                raise ApiError(
                    409, "PLAN_PENDING", "This thread has a plan awaiting a decision. POST /chat/decision first."
                )
            state.plan_approved = False  # every new request needs its plan approved
            self.planner.invoke(_user_input(message), config=config)
            return self._plan_outcome(thread_id, state)

    def decide(self, thread_id: str, approve: bool, feedback: str | None = None) -> ChatOutcome:
        self._require_agents()
        thread_id, state = self._thread(thread_id, "plan", create=False)
        with self._busy(thread_id, state):
            config = _config(thread_id)
            interrupts = self.planner.get_state(config).interrupts
            if not interrupts:
                raise ApiError(409, "NO_PENDING_PLAN", f"Thread '{thread_id}' has no plan awaiting a decision.")

            actions = interrupts[0].value["action_requests"]
            if approve:
                state.plan_approved = True
                decisions = [{"type": "approve"} for _ in actions]
            else:
                message = (
                    f"The user rejected this plan. Feedback: {feedback or 'No feedback given.'} "
                    "Revise the plan and call write_todos again."
                )
                decisions = [{"type": "reject", "message": message} for _ in actions]

            self.planner.invoke(Command(resume={"decisions": decisions}), config=config)
            return self._plan_outcome(thread_id, state)

    def _plan_outcome(self, thread_id: str, state: _ThreadState) -> ChatOutcome:
        """Auto-approve progress updates of an approved plan; stop at a new plan or the final reply."""
        config = _config(thread_id)
        while True:
            snapshot = self.planner.get_state(config)
            if not snapshot.interrupts:
                return ChatOutcome(thread_id, "plan", "completed", reply=_last_reply(snapshot.values))

            actions = snapshot.interrupts[0].value["action_requests"]
            if not state.plan_approved:
                todos = actions[0]["args"].get("todos", []) if actions else []
                plan = [{"content": t.get("content", ""), "status": t.get("status", "pending")} for t in todos]
                return ChatOutcome(thread_id, "plan", "awaiting_approval", plan=plan)

            approvals = [{"type": "approve"} for _ in actions]
            self.planner.invoke(Command(resume={"decisions": approvals}), config=config)
