"""Ticket Management agent: reads support tickets and proposes (never executes) ticket writes."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from agentic_rag.agents.base import SpecialistSpec
from agentic_rag.mcp_client import CrmToolkit

SPEC = SpecialistSpec(
    name="ticket_management",
    title="Ticket Management agent (support tickets)",
    description="Support ticket history and search (by customer, status, priority, product model, text). "
                "Proposes new tickets or resolutions, which a human approves before they are executed.",
    skills=("ticket-management",),
    system_prompt="""Look up support tickets with the read tools and report what the task needs.
You cannot write. When the task asks to raise or resolve a ticket, check the open tickets of that customer for a
duplicate first, then add a `proposed_actions` entry (register_ticket or resolve_ticket) with complete arguments,
following the ticket-management skill. Evidence uses kind "crm" with the ticket ID as ref.""",
    requires="crm",
)


def tools(crm: CrmToolkit) -> list[BaseTool]:
    """``get_tickets_by_customer`` and ``search_tickets`` (the write tools are kept by the graph)."""
    return list(crm.ticket_read)
