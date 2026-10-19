"""MCP resources: read-only JSON views of customers, tickets, the schema and ticket statistics."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError

from mcp_servers.crm_support.db import MAX_LIMIT, Repository
from mcp_servers.crm_support.models import TicketPriority, TicketStatus

READ_ONLY = {"readOnlyHint": True, "idempotentHint": True}

SCHEMA_DOC = {
    "entities": {
        "customer_profile": {
            "id_format": "CUST-0001",
            "fields": {
                "customer_id": "string, primary key",
                "full_name": "string",
                "communication_address": "string",
                "email": "string",
                "phone_number": "string",
                "credit_limit": "number, INR",
                "active_status": "boolean; inactive customers cannot raise tickets",
                "remarks": "string, optional",
                "created_at": "ISO-8601 UTC timestamp",
                "updated_at": "ISO-8601 UTC timestamp",
            },
        },
        "support_ticket": {
            "id_format": "TKT-000001",
            "fields": {
                "ticket_id": "string, primary key",
                "title": "string",
                "description": "string",
                "raised_by": "customer_id",
                "product_model": "string, optional (e.g. 'Lumina 55 Pro')",
                "status": [s.value for s in TicketStatus],
                "priority": [p.value for p in TicketPriority],
                "resolved_by": "string, set when resolved",
                "resolution_date": "ISO-8601 UTC timestamp, set when resolved",
                "resolution_remarks": "string, set when resolved",
                "created_at": "ISO-8601 UTC timestamp",
                "updated_at": "ISO-8601 UTC timestamp",
            },
        },
    },
    "rules": [
        "Customers cannot be created, updated or deleted through this server.",
        "Inactive customers cannot raise tickets.",
        "Only open or in_progress tickets can be resolved; resolved_by and resolution_remarks are required.",
        "A customer cannot have two open tickets with near-identical titles; the existing ticket is returned.",
        f"Searches are case-insensitive partial matches with at most {MAX_LIMIT} results per page.",
    ],
}


def register_resources(mcp: FastMCP, repo: Repository) -> None:
    """Register the resource templates and static resources on ``mcp``."""

    @mcp.resource("crm://customers/{customer_id}", mime_type="application/json", annotations=READ_ONLY,
                  tags={"customers"})
    def customer_profile(customer_id: str) -> dict:
        """The customer profile for ``customer_id``."""
        customer = repo.get_customer(customer_id)
        if customer is None:
            raise ResourceError(f"Customer '{customer_id}' was not found.")
        return customer.model_dump()

    @mcp.resource("crm://customers/{customer_id}/tickets", mime_type="application/json", annotations=READ_ONLY,
                  tags={"customers", "tickets"})
    def customer_tickets(customer_id: str) -> dict:
        """All tickets raised by ``customer_id``, newest first."""
        if repo.get_customer(customer_id) is None:
            raise ResourceError(f"Customer '{customer_id}' was not found.")
        tickets = repo.tickets_for_customer(customer_id)
        return {"customer_id": customer_id, "count": len(tickets), "tickets": [t.model_dump() for t in tickets]}

    @mcp.resource("tickets://{ticket_id}", mime_type="application/json", annotations=READ_ONLY, tags={"tickets"})
    def ticket(ticket_id: str) -> dict:
        """The full ticket ``ticket_id``, including resolution details."""
        found = repo.get_ticket(ticket_id)
        if found is None:
            raise ResourceError(f"Ticket '{ticket_id}' was not found.")
        return found.model_dump()

    @mcp.resource("crm://schema", mime_type="application/json", annotations=READ_ONLY, tags={"reference"})
    def schema() -> dict:
        """Data dictionary: fields, allowed status/priority values, ID formats and business rules."""
        return SCHEMA_DOC

    @mcp.resource("tickets://stats", mime_type="application/json", annotations=READ_ONLY, tags={"tickets"})
    def ticket_stats() -> dict:
        """Ticket counts by status and priority, oldest open tickets and models with most open issues."""
        return {**repo.counts(), **repo.ticket_stats()}
