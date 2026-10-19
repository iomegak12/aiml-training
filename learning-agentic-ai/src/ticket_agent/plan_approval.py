"""Plan -> human approval -> execute, using the write_todos interrupt."""

from collections.abc import Callable
from typing import Any

from langgraph.types import Command

from ticket_agent.streaming import stream_agent

STATUS_ICONS = {"pending": "⬜", "in_progress": "🔄", "completed": "✅"}


def print_todos(todos: list[dict[str, Any]], title: str) -> None:
    print(f"\n📋 {title}")
    for number, todo in enumerate(todos, start=1):
        icon = STATUS_ICONS.get(todo.get("status", "pending"), "⬜")
        print(f"   {icon} {number}. {todo.get('content', '')}")
    print()


def run_with_plan_approval(
    agent: Any,
    question: str,
    config: dict[str, Any],
    ask: Callable[[str], str] = input,
) -> None:
    """Ask the planning agent a question; show its plan and only execute once approved.

    The first plan (and any revised plan after a rejection) needs your approval.
    Once a plan is approved, later write_todos calls are progress updates and are
    approved automatically.

    Args:
        agent: Agent from build_planning_agent().
        question: The user's request.
        config: Thread config, e.g. new_thread().
        ask: Prompt function (defaults to input()).
    """
    payload: Any = question
    plan_approved = False

    while interrupts := stream_agent(agent, payload, config):
        decisions = []
        for action in interrupts[0].value["action_requests"]:
            todos = action["args"].get("todos", [])

            if plan_approved:
                print_todos(todos, "Plan progress (auto-approved)")
                decisions.append({"type": "approve"})
                continue

            print_todos(todos, "Proposed plan")
            answer = ask("Approve this plan? (y/n): ").strip().lower()
            if answer in ("y", "yes"):
                plan_approved = True
                print("✅ Plan approved, executing...\n")
                decisions.append({"type": "approve"})
            else:
                feedback = ask("What should change in the plan? ").strip() or "No feedback given."
                print("❌ Plan rejected, asking the agent to revise...\n")
                decisions.append(
                    {
                        "type": "reject",
                        "message": f"The user rejected this plan. Feedback: {feedback} "
                        "Revise the plan and call write_todos again.",
                    }
                )

        payload = Command(resume={"decisions": decisions})
