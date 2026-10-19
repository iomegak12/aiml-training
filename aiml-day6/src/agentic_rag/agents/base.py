"""Building and running a specialist Deep Agent.

Every specialist is a ``create_deep_agent`` agent with:

- **only its own tools** (RAG pipelines, MCP tools or web search),
- **only its own skills**: each skill folder in ``src/skills`` is mounted read-only into the
  agent's virtual filesystem (``/hr-policies/``, ``/rag-answering/`` ...) through a
  ``CompositeBackend``; scratch files the agent writes stay in its state,
- the specialist model (low reasoning effort - the Coordinator does the deep thinking),
- a structured ``AgentReportDraft`` as its final response.

The Deep Agents harness adds planning (``write_todos``), file tools, and automatic
summarisation of long tool outputs - the specialist's context stays isolated from the
other agents and from the Coordinator, which only ever sees the compact report.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from deepagents import (
    FilesystemPermission,
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from agentic_rag.agents.reports import AgentReport, AgentReportDraft
from agentic_rag.config import AgentSettings
from agentic_rag.llm import specialist_llm

REPORT_INSTRUCTIONS = """
## How you work
- You are one specialist in a team run by a Coordinator. Do ONLY the task you are given, with your own tools.
- Your skills (listed below) contain the domain rules - read the relevant SKILL.md before your first search.
- Keep tool calls focused: usually 1-3 calls. Do not repeat an identical call.
- Finish with your structured report: concise `findings`, `evidence` with exact quotes and references,
  honest `confidence`, and `gaps` for anything you could not find. Never invent facts, IDs or numbers.
"""

_registered_profiles: set[str] = set()


@dataclass(frozen=True)
class SpecialistSpec:
    """Static description of a specialist.

    Attributes:
        name: Identifier used in plans (``hr_policy``, ``product_manuals`` ...).
        title: Human-readable name.
        description: What the agent can do - shown to the Coordinator when planning.
        skills: Skill folder names in ``src/skills`` mounted for this agent.
        system_prompt: Role-specific instructions.
        requires: External dependency (``crm`` MCP server or ``serper`` key), if any.
    """

    name: str
    title: str
    description: str
    skills: tuple[str, ...]
    system_prompt: str
    requires: Literal["crm", "serper"] | None = None


def _register_profile(settings: AgentSettings) -> None:
    """Turn off the default ``task`` subagent and ``execute`` tool for the specialist model.

    Specialists are leaf agents: delegation is the Coordinator's job, and there is no sandbox.
    """
    key = f"openai:{settings.specialist_model}"
    if key not in _registered_profiles:
        register_harness_profile(key, HarnessProfile(
            excluded_tools=frozenset({"execute"}),
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ))
        _registered_profiles.add(key)


def skills_backend(settings: AgentSettings, skills: Sequence[str]) -> CompositeBackend:
    """Mount each skill folder at ``/<skill>/``; everything else lives in the agent's state."""
    routes = {f"/{name}/": FilesystemBackend(root_dir=settings.skills_dir / name, virtual_mode=True)
              for name in skills}
    return CompositeBackend(default=StateBackend(), routes=routes)


def build_specialist(spec: SpecialistSpec, settings: AgentSettings, tools: Sequence[BaseTool]) -> CompiledStateGraph:
    """Create the Deep Agent for ``spec`` with ``tools``, its skills (read-only) and a structured report."""
    _register_profile(settings)
    missing = [s for s in spec.skills if not (settings.skills_dir / s / "SKILL.md").is_file()]
    if missing:
        raise FileNotFoundError(f"{spec.name}: skills not found in {settings.skills_dir}: {missing}")
    return create_deep_agent(
        model=specialist_llm(settings),
        tools=list(tools),
        system_prompt=f"You are the {spec.title}.\n{spec.system_prompt.strip()}\n{REPORT_INSTRUCTIONS}",
        skills=["/"],
        backend=skills_backend(settings, spec.skills),
        permissions=[FilesystemPermission(operations=["write"], paths=[f"/{s}/**" for s in spec.skills],
                                          mode="deny")],
        response_format=ToolStrategy(AgentReportDraft),
        name=spec.name,
    )


def task_message(question: str, step_id: str, goal: str, success_criteria: str = "", notes: str = "") -> str:
    """The message a specialist receives: its goal, the user's question and relevant earlier findings."""
    parts = [f"Task {step_id}: {goal}"]
    if success_criteria:
        parts.append(f"Done when: {success_criteria}")
    parts.append(f"Original user question (for context only - answer just your task): {question}")
    if notes:
        parts.append(f"Findings from earlier steps you can use:\n{notes}")
    return "\n\n".join(parts)


async def run_specialist(agent: CompiledStateGraph, agent_name: str, step_id: str, goal: str, message: str,
                         timeout_s: float = 300, recursion_limit: int = 40) -> AgentReport:
    """Run ``agent`` on ``message`` and return its ``AgentReport`` (errors become a zero-confidence report)."""
    started = time.time()
    try:
        state = await asyncio.wait_for(
            agent.ainvoke({"messages": [HumanMessage(message)]}, config={"recursion_limit": recursion_limit}),
            timeout=timeout_s)
        draft = state.get("structured_response")
        if draft is None:
            raise RuntimeError("agent finished without a structured report")
        if isinstance(draft, dict):
            draft = AgentReportDraft.model_validate(draft)
        return AgentReport(**draft.model_dump(), agent=agent_name, step_id=step_id, goal=goal,
                           started_at=started, finished_at=time.time())
    except Exception as exc:  # noqa: BLE001 - a failing specialist must not crash the whole graph
        error = f"{type(exc).__name__}: {exc}"[:500]
        return AgentReport(findings=f"The {agent_name} agent failed: {error}", confidence=0.0,
                           gaps=[f"{agent_name} could not complete: {goal}"], agent=agent_name, step_id=step_id,
                           goal=goal, started_at=started, finished_at=time.time(), error=error)
