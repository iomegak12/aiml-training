"""MCP tools: read and search customer profiles, read/search/register/resolve support tickets.

There are deliberately no tools to create, update or delete customers. Business-rule
violations are returned to the client as ``ToolError`` messages.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_servers.crm_support import rules
from mcp_servers.crm_support.db import Repository
from mcp_servers.crm_support.models import (
    OPEN_STATUSES,
    CustomerProfile,
    CustomerSearchResult,
    RegisterTicketResult,
    SupportTicket,
    TicketPriority,
    TicketSearchResult,
    TicketStatus,
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)


def register_tools(mcp: FastMCP, repo: Repository) -> None:
    """Register all CRM and ticket tools on ``mcp`` using ``repo`` for data access."""

    def guarded(fn, *args, **kwargs):
        """Run a repository call, turning business-rule violations into MCP tool errors."""
        try:
            return fn(*args, **kwargs)
        except rules.BusinessRuleError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(tags={"customers"}, annotations=READ_ONLY)
    def get_customer_profile(
        customer_id: Annotated[str, Field(description="Customer profile ID, e.g. CUST-0001")],
    ) -> CustomerProfile:
        """Fetch one customer profile by its profile ID."""
        customer = repo.get_customer(customer_id)
        if customer is None:
            raise ToolError(f"Customer '{customer_id}' was not found.")
        return customer

    @mcp.tool(tags={"customers"}, annotations=READ_ONLY)
    def search_customer_profiles(
        name: Annotated[str | None, Field(description="Part of the full name, case-insensitive")] = None,
        email: Annotated[str | None, Field(description="Part of the email address")] = None,
        phone: Annotated[str | None, Field(description="Part of the phone number")] = None,
        address: Annotated[str | None, Field(description="Part of the address, e.g. a city or PIN code")] = None,
        active_status: Annotated[bool | None, Field(description="True for active, False for inactive")] = None,
        min_credit: Annotated[float | None, Field(description="Minimum credit limit (INR)")] = None,
        max_credit: Annotated[float | None, Field(description="Maximum credit limit (INR)")] = None,
        limit: Annotated[int, Field(description="Page size, 1-100", ge=1, le=100)] = 20,
        offset: Annotated[int, Field(description="Number of results to skip", ge=0)] = 0,
    ) -> CustomerSearchResult:
        """Search customer profiles by common attributes. Text filters are partial and case-insensitive."""
        total, customers = repo.search_customers(
            name=name, email=email, phone=phone, address=address, active_status=active_status,
            min_credit=min_credit, max_credit=max_credit, limit=limit, offset=offset)
        return CustomerSearchResult(total=total, count=len(customers), customers=customers)

    @mcp.tool(tags={"tickets"}, annotations=READ_ONLY)
    def get_tickets_by_customer(
        customer_id: Annotated[str, Field(description="Customer profile ID, e.g. CUST-0001")],
        status: Annotated[str | None, Field(description="Optional status: open, in_progress, resolved, closed")] = None,
    ) -> TicketSearchResult:
        """List the support tickets raised by a customer, newest first."""
        status = guarded(rules.validate_enum, status, TicketStatus, "status")
        if repo.get_customer(customer_id) is None:
            raise ToolError(f"Customer '{customer_id}' was not found.")
        tickets = repo.tickets_for_customer(customer_id, status)
        return TicketSearchResult(total=len(tickets), count=len(tickets), tickets=tickets)

    @mcp.tool(tags={"tickets"}, annotations=READ_ONLY)
    def search_tickets(
        text: Annotated[str | None, Field(description="Keywords; every word must appear in the title or description (partial, case-insensitive)")] = None,
        status: Annotated[str | None, Field(description="open, in_progress, resolved or closed")] = None,
        priority: Annotated[str | None, Field(description="low, medium, high or critical")] = None,
        raised_by: Annotated[str | None, Field(description="Customer profile ID")] = None,
        product_model: Annotated[str | None, Field(description="Product model or part of it, e.g. 'Z9 Plus' (a leading brand is ignored)")] = None,
        resolved_by: Annotated[str | None, Field(description="Part of the resolver's name")] = None,
        created_from: Annotated[str | None, Field(description="ISO date, e.g. 2026-06-01")] = None,
        created_to: Annotated[str | None, Field(description="ISO date, e.g. 2026-06-30")] = None,
        limit: Annotated[int, Field(description="Page size, 1-100", ge=1, le=100)] = 20,
        offset: Annotated[int, Field(description="Number of results to skip", ge=0)] = 0,
    ) -> TicketSearchResult:
        """Search support tickets by common attributes. Text filters are partial and case-insensitive."""
        status = guarded(rules.validate_enum, status, TicketStatus, "status")
        priority = guarded(rules.validate_enum, priority, TicketPriority, "priority")
        total, tickets = repo.search_tickets(
            text=text, status=status, priority=priority, raised_by=raised_by, product_model=product_model,
            resolved_by=resolved_by, created_from=created_from, created_to=created_to, limit=limit, offset=offset)
        return TicketSearchResult(total=total, count=len(tickets), tickets=tickets)

    @mcp.tool(tags={"tickets", "write"}, annotations=WRITE)
    def register_ticket(
        customer_id: Annotated[str, Field(description="Customer profile ID raising the ticket")],
        title: Annotated[str, Field(description="Short summary of the issue")],
        description: Annotated[str, Field(description="Detailed description of the issue")],
        priority: Annotated[str, Field(description="low, medium, high or critical")] = "medium",
        product_model: Annotated[str | None, Field(description="Product model, e.g. 'Lumina 55 Pro'")] = None,
    ) -> RegisterTicketResult:
        """Register a new support ticket for an active customer.

        If the customer already has an open ticket with a near-identical title, no new ticket
        is created and the existing one is returned (``created = false``).
        """
        def _register() -> RegisterTicketResult:
            level = rules.validate_enum(priority, TicketPriority, "priority") or TicketPriority.MEDIUM.value
            customer = rules.require_active(repo.get_customer(customer_id), customer_id)
            clean_title = rules.require_text(title, "title")
            clean_description = rules.require_text(description, "description", min_length=10)
            open_tickets = [t for t in repo.tickets_for_customer(customer.customer_id) if t.status in OPEN_STATUSES]
            duplicate = rules.find_duplicate(clean_title, open_tickets)
            if duplicate:
                return RegisterTicketResult(
                    created=False, ticket=duplicate,
                    message=f"Customer already has open ticket {duplicate.ticket_id} with a similar title; "
                            "no duplicate was created.")
            ticket = repo.insert_ticket(title=clean_title, description=clean_description,
                                        raised_by=customer.customer_id, priority=level, product_model=product_model)
            return RegisterTicketResult(created=True, ticket=ticket,
                                        message=f"Ticket {ticket.ticket_id} registered with priority '{level}'.")

        return guarded(_register)

    @mcp.tool(tags={"tickets", "write"}, annotations=WRITE)
    def resolve_ticket(
        ticket_id: Annotated[str, Field(description="Ticket ID, e.g. TKT-000042")],
        resolved_by: Annotated[str, Field(description="Name of the person or agent resolving the ticket")],
        resolution_remarks: Annotated[str, Field(description="What was done to resolve the issue")],
    ) -> SupportTicket:
        """Resolve an open or in-progress ticket; sets the resolution date to now."""
        def _resolve() -> SupportTicket:
            ticket = rules.require_resolvable(repo.get_ticket(ticket_id), ticket_id)
            who = rules.require_text(resolved_by, "resolved_by", min_length=2)
            remarks = rules.require_text(resolution_remarks, "resolution_remarks", min_length=10)
            return repo.mark_resolved(ticket.ticket_id, who, remarks)

        return guarded(_resolve)
