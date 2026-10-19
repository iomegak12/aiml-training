"""Assemble and compile the Coordinator ``StateGraph``; export it as a Mermaid diagram."""

from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore

from agentic_rag.agents.registry import Specialist
from agentic_rag.config import AgentSettings
from agentic_rag.graph.nodes import Coordinator
from agentic_rag.graph.state import CoordinatorState, StepInput
from agentic_rag.mcp_client import CrmToolkit


def build_graph(settings: AgentSettings, team: dict[str, Specialist], crm: CrmToolkit,
                checkpointer: BaseCheckpointSaver | None = None, store: BaseStore | None = None) -> CompiledStateGraph:
    """Build the plan -> parallel dispatch -> reflect -> approve -> synthesize -> judge graph.

    Args:
        settings: Agent settings (budgets, judge thresholds, models).
        team: Specialists from :func:`agentic_rag.agents.registry.build_team`.
        crm: CRM MCP toolkit (its write tools are used only by ``execute_actions``).
        checkpointer: Short-term memory; required for interrupts (clarify, approve) and follow-ups.
        store: Long-term memory store used by ``load_memory`` and ``save_memory``.
    """
    c = Coordinator(settings, team, crm)
    graph = StateGraph(CoordinatorState)
    graph.add_node("start_turn", c.start_turn)
    graph.add_node("load_memory", c.load_memory)
    graph.add_node("plan", c.plan)
    graph.add_node("clarify", c.clarify)
    graph.add_node("run_step", c.run_step, input_schema=StepInput)
    graph.add_node("reflect", c.reflect)
    graph.add_node("approve_actions", c.approve_actions)
    graph.add_node("execute_actions", c.execute_actions)
    graph.add_node("synthesize", c.synthesize)
    graph.add_node("judge", c.judge)
    graph.add_node("finalize", c.finalize)
    graph.add_node("save_memory", c.save_memory)

    graph.add_edge(START, "start_turn")
    graph.add_edge("start_turn", "load_memory")
    graph.add_edge("load_memory", "plan")
    graph.add_conditional_edges("plan", c.route_after_plan, ["clarify", "run_step", "approve_actions", "synthesize"])
    graph.add_edge("clarify", "plan")
    graph.add_edge("run_step", "reflect")
    graph.add_conditional_edges("reflect", c.route_after_reflect,
                                ["run_step", "plan", "approve_actions", "synthesize"])
    graph.add_edge("approve_actions", "execute_actions")
    graph.add_edge("execute_actions", "synthesize")
    graph.add_edge("synthesize", "judge")
    graph.add_conditional_edges("judge", c.route_after_judge, ["plan", "finalize"])
    graph.add_edge("finalize", "save_memory")
    graph.add_edge("save_memory", END)
    return graph.compile(checkpointer=checkpointer, store=store, name="coordinator")


def mermaid(graph: CompiledStateGraph) -> str:
    """Mermaid source of the compiled graph (``get_graph().draw_mermaid()``)."""
    return graph.get_graph().draw_mermaid()


def export_mermaid(graph: CompiledStateGraph, path: Path) -> Path:
    """Write the graph's Mermaid diagram to ``path`` (a ``.mmd`` file) and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mermaid(graph), encoding="utf-8")
    return path
