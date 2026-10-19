"""State and structured outputs of the Coordinator graph.

The state is a ``TypedDict`` checkpointed after every node (short-term memory). Lists that
parallel branches write to (``reports``, ``completed``) use an *accumulate* reducer so that
specialists running at the same time never overwrite each other. Sending ``None`` resets
such a field, which ``start_turn`` does at the start of every new question on a thread.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


def accumulate(left: list | None, right: list | None) -> list:
    """Reducer: append ``right`` to ``left``; ``None`` resets the list."""
    if right is None:
        return []
    return (left or []) + list(right)


def add_count(left: int | None, right: int | None) -> int:
    """Reducer: add ``right`` to ``left``; ``None`` resets the counter to 0."""
    if right is None:
        return 0
    return (left or 0) + right


class PlanStep(BaseModel):
    """One unit of work for one specialist."""

    id: str = Field(description="Short step ID, e.g. 's1'")
    agent: str = Field(description="Specialist name, e.g. 'hr_policy'")
    goal: str = Field(description="Precise task including identifiers (customer ID, product model, policy)")
    rationale: str = Field(default="", description="Why this step is needed")
    depends_on: list[str] = Field(default_factory=list, description="IDs of steps whose output this step needs")
    success_criteria: str = Field(default="", description="What a complete result contains")


class Plan(BaseModel):
    """The Coordinator's plan (or a clarifying question instead)."""

    reasoning: str = Field(description="Two or three sentences: how the question breaks down and why these agents")
    clarifying_question: str | None = Field(
        default=None, description="Ask the user ONLY if essential information cannot be looked up; else null")
    steps: list[PlanStep] = Field(default_factory=list)


class Reflection(BaseModel):
    """Decision after all planned steps have reported."""

    decision: Literal["synthesize", "replan"]
    reason: str
    gaps: list[str] = Field(default_factory=list, description="Concrete missing information worth another step")


class UserFacts(BaseModel):
    """Durable facts about the user worth remembering across conversations."""

    facts: list[str] = Field(default_factory=list,
                             description="Short third-person facts, e.g. 'Customer ID is CUST-0001'")


class StepInput(TypedDict):
    """Payload sent to ``run_step`` for one plan step (via ``Send``)."""

    step: dict[str, Any]
    question: str
    notes: str


class CoordinatorState(TypedDict, total=False):
    """Everything the Coordinator graph tracks for a thread.

    Turn inputs: ``messages`` (conversation, short-term memory) and ``user_id``.
    Per-turn fields are reset by ``start_turn``.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    question: str
    history: str
    memories: list[str]
    clarifications: list[dict[str, str]]
    clarifying_question: str | None
    plan: list[dict[str, Any]]
    plan_history: Annotated[list[dict[str, Any]], accumulate]
    reports: Annotated[list[dict[str, Any]], accumulate]
    completed: Annotated[list[str], accumulate]
    agent_calls: Annotated[int, add_count]
    replans: int
    reflection: dict[str, Any]
    decided_actions: Annotated[list[dict[str, Any]], accumulate]
    executed_actions: Annotated[list[str], accumulate]
    draft_answer: str
    attempts: Annotated[list[dict[str, Any]], accumulate]
    judge_feedback: str
    final: dict[str, Any]
