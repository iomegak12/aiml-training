"""MCP prompts: reusable instructions that embed live CRM data."""

from __future__ import annotations

import json

from fastmcp import FastMCP
from fastmcp.exceptions import PromptError

from mcp_servers.crm_support.db import Repository


def _as_json(data) -> str:
    """Pretty JSON for embedding records in a prompt."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def register_prompts(mcp: FastMCP, repo: Repository) -> None:
    """Register the support prompts on ``mcp``."""

    @mcp.prompt(tags={"tickets"})
    def triage_ticket(ticket_id: str) -> str:
        """Triage a ticket: assess urgency, suggest a priority and point to the right manual section.

        Args:
            ticket_id: Ticket to triage, e.g. TKT-000001.
        """
        ticket = repo.get_ticket(ticket_id)
        if ticket is None:
            raise PromptError(f"Ticket '{ticket_id}' was not found.")
        customer = repo.get_customer(ticket.raised_by)
        return (
            "You are a senior support engineer. Triage the support ticket below.\n\n"
            f"TICKET:\n{_as_json(ticket.model_dump())}\n\n"
            f"CUSTOMER:\n{_as_json(customer.model_dump() if customer else {})}\n\n"
            "Respond with:\n"
            "1. Urgency assessment (one paragraph) and the business impact.\n"
            "2. Suggested priority (low, medium, high or critical) and why, compared with the current priority.\n"
            "3. Which section of the product's user manual to consult (e.g. Error Codes, Troubleshooting, "
            "Warranty and Service), and the exact error code or symptom to look up.\n"
            "4. The next action for the support team.\n"
            "Do not invent product facts; say what must be checked in the manual."
        )

    @mcp.prompt(tags={"customers"})
    def customer_360_summary(customer_id: str) -> str:
        """Summarise a customer: profile, ticket history, open issues and the next best action.

        Args:
            customer_id: Customer profile ID, e.g. CUST-0001.
        """
        customer = repo.get_customer(customer_id)
        if customer is None:
            raise PromptError(f"Customer '{customer_id}' was not found.")
        tickets = [t.model_dump() for t in repo.tickets_for_customer(customer.customer_id)]
        return (
            "You are a customer success manager. Write a concise 360-degree summary of this customer.\n\n"
            f"PROFILE:\n{_as_json(customer.model_dump())}\n\n"
            f"TICKETS ({len(tickets)}):\n{_as_json(tickets)}\n\n"
            "Cover: who the customer is (status, credit limit, remarks), products mentioned in tickets, "
            "open issues with priorities, recurring problems, how quickly past tickets were resolved, "
            "and one recommended next best action. Use bullet points and cite ticket IDs."
        )
