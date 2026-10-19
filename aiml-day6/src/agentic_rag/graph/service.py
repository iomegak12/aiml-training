"""High-level async API over the Coordinator graph: ``ask`` and ``resume``.

Example (in a notebook)::

    async with CoordinatorService.open() as service:
        result = await service.ask("How many casual leaves do I get?", user_id="emp-42")
        if result.status == "needs_approval":
            result = await service.resume(result.thread_id, "approve")
        print(result.answer)

``open()`` opens the SQLite memory, loads the CRM MCP tools (the CRM agents are marked
unavailable when the server is down), builds the five specialists and compiles the graph.
In a notebook, ``service = await CoordinatorService.create()`` keeps it open across cells
(``await service.aclose()`` at the end), and a ``GraphResult`` renders as Markdown.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from agentic_rag.agents.registry import Specialist, build_team, roster
from agentic_rag.config import AgentSettings
from agentic_rag.graph.builder import build_graph, mermaid
from agentic_rag.mcp_client import CrmToolkit, load_crm_tools
from agentic_rag.memory import Memory, forget_user, open_memory, recall_facts

Status = Literal["completed", "needs_clarification", "needs_approval"]


@dataclass
class GraphResult:
    """Outcome of ``ask`` / ``resume``: a final answer, or a pending interrupt to answer with ``resume``.

    Attributes:
        thread_id: Conversation ID (pass it to ``resume`` and to follow-up ``ask`` calls).
        status: ``completed``, ``needs_clarification`` or ``needs_approval``.
        answer: Final answer (empty while interrupted).
        interrupt: Interrupt payload (the clarifying question, or the actions awaiting approval).
        final: Score, pass/low-confidence flags, attempts, evidence list.
        plan_history: Every plan/replan round with the Coordinator's reasoning.
        reports: Specialist reports (findings, evidence, confidence, timings).
        attempts: Judge attempts (answer, scores, critique).
        actions: Ticket actions with the human decision.
        elapsed_s: Wall-clock seconds of this call.
    """

    thread_id: str
    status: Status
    answer: str = ""
    interrupt: dict[str, Any] | None = None
    final: dict[str, Any] = field(default_factory=dict)
    plan_history: list[dict[str, Any]] = field(default_factory=list)
    reports: list[dict[str, Any]] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    elapsed_s: float = 0.0

    def timeline(self) -> str:
        """Specialist runs with start/end offsets - overlapping bars show parallel execution."""
        runs = [r for r in self.reports if r.get("agent") != "coordinator"]
        if not runs:
            return "(no specialist runs)"
        t0 = min(r["started_at"] for r in runs)
        span = max(r["finished_at"] for r in runs) - t0 or 1
        lines = []
        for r in sorted(runs, key=lambda r: r["started_at"]):
            a, b = r["started_at"] - t0, r["finished_at"] - t0
            bar = " " * int(40 * a / span) + "#" * max(1, int(40 * (b - a) / span))
            lines.append(f"{r['step_id']:>6} {r['agent']:<18} {a:6.1f}s -> {b:6.1f}s |{bar:<40}|")
        return "\n".join(lines)

    def summary(self) -> str:
        """Readable multi-line summary: status, plan rounds, timeline, judge attempts and the answer."""
        out = [f"thread={self.thread_id} status={self.status} elapsed={self.elapsed_s:.1f}s"]
        for p in self.plan_history:
            steps = ", ".join(f"{s['id']}:{s['agent']}" + (f"<-{s['depends_on']}" if s.get("depends_on") else "")
                              for s in p.get("steps", []))
            out.append(f"plan round {p['round']} ({p['trigger']}): {steps or p.get('clarifying_question') or 'no steps'}")
        if self.reports:
            out.append("timeline:\n" + self.timeline())
        for a in self.attempts:
            out.append(f"judge attempt {a['attempt']}: {a['summary']}")
        if self.interrupt:
            out.append(f"INTERRUPT: {self.interrupt}")
        if self.answer:
            out.append("\n" + self.answer)
        return "\n".join(out)

    def _repr_markdown_(self) -> str:
        """Notebook rendering: run facts, plan rounds, timeline and judge attempts, then the answer as Markdown."""
        facts = [f"**status** `{self.status}` | **thread** `{self.thread_id}` | **elapsed** {self.elapsed_s:.1f}s"]
        if self.final:
            facts.append(f"**judge** {self.final.get('score')}/100 | **passed** {self.final.get('passed')} | "
                         f"**attempts** {self.final.get('attempts')} | **specialist runs** "
                         f"{self.final.get('agent_calls')}")
        details = "\n".join(self.summary().split("\n\n")[0].splitlines()[1:])
        body = f"\n\n```text\n{details}\n```" if details else ""
        if self.interrupt:
            body += f"\n\n**Waiting for you:** `{self.interrupt}`"
        return "  \n".join(facts) + body + (f"\n\n---\n\n{self.answer}" if self.answer else "")


class CoordinatorService:
    """Owns the compiled graph, the team and the memory for the lifetime of an ``async with`` block."""

    def __init__(self, settings: AgentSettings, graph: CompiledStateGraph, team: dict[str, Specialist],
                 crm: CrmToolkit, memory: Memory) -> None:
        """Use :meth:`open` instead of calling this directly."""
        self.settings = settings
        self.graph = graph
        self.team = team
        self.crm = crm
        self.memory = memory
        self._stack: AsyncExitStack | None = None

    @classmethod
    @asynccontextmanager
    async def open(cls, settings: AgentSettings | None = None) -> AsyncIterator[CoordinatorService]:
        """Open memory, load MCP tools, build the team and compile the graph."""
        settings = settings or AgentSettings.load()
        async with open_memory(settings) as memory:
            crm = await load_crm_tools(settings)
            team = build_team(settings, crm)
            graph = build_graph(settings, team, crm, checkpointer=memory.checkpointer, store=memory.store)
            yield cls(settings, graph, team, crm, memory)

    @classmethod
    async def create(cls, settings: AgentSettings | None = None) -> CoordinatorService:
        """Open the service without an ``async with`` block (handy in notebooks); call :meth:`aclose` when done."""
        stack = AsyncExitStack()
        service = await stack.enter_async_context(cls.open(settings))
        service._stack = stack
        return service

    async def aclose(self) -> None:
        """Close the memory databases opened by :meth:`create`."""
        if self._stack:
            await self._stack.aclose()
            self._stack = None

    def roster(self) -> str:
        """The team and each agent's availability."""
        return roster(self.team)

    def mermaid(self) -> str:
        """Mermaid diagram of the compiled graph."""
        return mermaid(self.graph)

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        """Run configuration for ``thread_id``."""
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 120}

    async def _run(self, graph_input: Any, thread_id: str, on_event: Callable[[str], None] | None) -> GraphResult:
        """Stream the graph to completion or the next interrupt, reporting node updates to ``on_event``."""
        started = time.time()
        config = self._config(thread_id)
        async for chunk in self.graph.astream(graph_input, config, stream_mode="updates"):
            if on_event:
                for node, update in chunk.items():
                    on_event(describe_update(node, update, time.time() - started))
        return await self._result(thread_id, time.time() - started)

    async def ask(self, question: str, thread_id: str | None = None, user_id: str = "demo-user",
                  on_event: Callable[[str], None] | None = None) -> GraphResult:
        """Ask a question on ``thread_id`` (a new thread when omitted). ``on_event=print`` shows live progress."""
        thread_id = thread_id or f"thread-{uuid.uuid4().hex[:8]}"
        return await self._run({"messages": [HumanMessage(question)], "user_id": user_id}, thread_id, on_event)

    async def resume(self, thread_id: str, value: Any, on_event: Callable[[str], None] | None = None) -> GraphResult:
        """Answer a pending interrupt: the clarification text, or ``approve``/``reject``/per-action decisions."""
        return await self._run(Command(resume=value), thread_id, on_event)

    async def _result(self, thread_id: str, elapsed: float) -> GraphResult:
        """Build a ``GraphResult`` from the thread's latest checkpoint."""
        snapshot = await self.graph.aget_state(self._config(thread_id))
        values = snapshot.values
        common = {"thread_id": thread_id, "plan_history": values.get("plan_history", []),
                  "reports": values.get("reports", []), "attempts": values.get("attempts", []),
                  "actions": values.get("decided_actions", []), "elapsed_s": elapsed}
        if snapshot.interrupts:
            payload = snapshot.interrupts[0].value
            status: Status = "needs_approval" if payload.get("type") == "approval" else "needs_clarification"
            return GraphResult(status=status, interrupt=payload, **common)
        final = values.get("final", {})
        return GraphResult(status="completed", answer=final.get("answer", ""), final=final, **common)

    async def history(self, thread_id: str) -> list[tuple[str, str]]:
        """The conversation of ``thread_id`` as ``(role, text)`` pairs."""
        snapshot = await self.graph.aget_state(self._config(thread_id))
        return [(m.type, m.text if isinstance(m.text, str) else str(m.content))
                for m in snapshot.values.get("messages", [])]

    async def recall(self, user_id: str) -> list[str]:
        """Long-term facts remembered about ``user_id``."""
        return await recall_facts(self.memory.store, user_id)

    async def forget(self, user_id: str) -> int:
        """Delete the long-term facts about ``user_id``."""
        return await forget_user(self.memory.store, user_id)


def describe_update(node: str, update: Any, elapsed: float) -> str:
    """One progress line for a node update (used for live output in notebooks)."""
    prefix = f"[{elapsed:6.1f}s] {node:<15}"
    if node == "__interrupt__":
        payload = update[0].value if update else {}
        return f"{prefix} PAUSED for {payload.get('type')}: {payload.get('question') or payload.get('actions')}"
    update = update or {}
    if node == "plan":
        history = update.get("plan_history", [{}])[-1]
        if history.get("clarifying_question"):
            return f"{prefix} needs clarification: {history['clarifying_question']}"
        steps = ", ".join(f"{s['id']}={s['agent']}" for s in history.get("steps", []))
        return f"{prefix} {history.get('trigger', '')} -> {steps or 'no new steps'}"
    if node == "run_step":
        r = update["reports"][0]
        return (f"{prefix} {r['step_id']} {r['agent']} done in {r['finished_at'] - r['started_at']:.1f}s "
                f"(confidence {r['confidence']:.2f}, {len(r['evidence'])} evidence, "
                f"{len(r['proposed_actions'])} proposed actions)")
    if node == "reflect":
        ref = update.get("reflection", {})
        return f"{prefix} {ref.get('decision')}: {ref.get('reason', '')[:120]}"
    if node == "judge":
        a = update["attempts"][0]
        return f"{prefix} attempt {a['attempt']}: {a['summary']}"
    if node == "load_memory":
        return f"{prefix} {len(update.get('memories', []))} long-term facts recalled"
    if node == "execute_actions":
        return f"{prefix} {update['reports'][0]['findings'][:150]}"
    return f"{prefix} done"
