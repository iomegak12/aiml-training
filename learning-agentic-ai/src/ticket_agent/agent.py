"""Deep agent construction: one agent for direct execution and one that plans first."""

from typing import Any
from uuid import uuid4

from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from agent_tools import LOCAL_TOOLS, build_ticket_tools
from it_tickets import TicketService
from ticket_agent.model import build_model
from ticket_agent.settings import AgentSettings

SYSTEM_PROMPT = """You are an IT support assistant.

You manage IT support tickets with the ticket tools:
- register_ticket, find_tickets, get_ticket, update_ticket, resolve_ticket, archive_ticket.
- Ticket statuses: Open -> In Progress -> Resolved -> Archived. Use update_ticket to move
  between Open and In Progress, resolve_ticket to resolve, and archive_ticket to archive a
  resolved ticket.
- Priorities: Low, Medium, High, Critical.
- Never invent ticket IDs or ticket data; always use the tools.
- If a tool returns an "error", explain the problem to the user in plain language and,
  where possible, what they can do instead.

You also have local tools: get_location (the user's current location), get_weather(city)
and get_current_time(timezone). When the user says "where I am" or "my location", call
get_location first and use its city / timezone.

Keep answers concise. When showing tickets, include the ticket ID, title, priority,
department and status."""

PLANNING_PROMPT = """

## Planning
Before calling any other tool, call `write_todos` once with your complete step-by-step
plan for the user's request. The user reviews every `write_todos` call before it runs:
- If the `write_todos` call succeeds, the user has APPROVED the plan. Immediately execute
  it with the tools, step by step. Do not ask for confirmation again and do not repeat the
  plan; finish with the final answer.
- If the call is rejected, read the user's feedback, revise the plan and call
  `write_todos` again with the revised plan."""


def build_tools(ticket_service: TicketService | None = None) -> list[BaseTool]:
    """All tools attached to the agent: IT ticket tools + local tools."""
    return [*build_ticket_tools(ticket_service), *LOCAL_TOOLS]


def build_agent(
    *,
    settings: AgentSettings | None = None,
    model: BaseChatModel | None = None,
    ticket_service: TicketService | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Deep agent with all tools and conversation memory (use a thread_id config)."""
    return create_deep_agent(
        model=model or build_model(settings),
        tools=build_tools(ticket_service),
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer or InMemorySaver(),
    )


def build_planning_agent(
    *,
    settings: AgentSettings | None = None,
    model: BaseChatModel | None = None,
    ticket_service: TicketService | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Deep agent that writes a todo plan first and pauses for approval on write_todos."""
    return create_deep_agent(
        model=model or build_model(settings),
        tools=build_tools(ticket_service),
        system_prompt=SYSTEM_PROMPT + PLANNING_PROMPT,
        middleware=[TodoListMiddleware()],
        interrupt_on={"write_todos": {"allowed_decisions": ["approve", "reject"]}},
        checkpointer=checkpointer or InMemorySaver(),  # required for human-in-the-loop
    )


def new_thread() -> dict[str, Any]:
    """Config for a new conversation thread."""
    return {"configurable": {"thread_id": str(uuid4())}}
