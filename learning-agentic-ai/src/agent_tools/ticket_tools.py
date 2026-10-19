"""LangChain tools that expose the it_tickets library to an agent.

The library itself is used as-is; these tools only wrap TicketService calls and
turn library errors into `{"error": ...}` results the agent can read and explain.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any, Literal

from langchain_core.tools import BaseTool, tool
from pydantic import ValidationError

from it_tickets import TicketError, TicketService

PriorityValue = Literal["Low", "Medium", "High", "Critical"]
ActiveStatusValue = Literal["Open", "In Progress"]


def _error_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'input'}: {err['msg']}"
            for err in exc.errors()
        )
    return str(exc)


def _returns_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Return library / validation errors to the agent instead of raising."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except (TicketError, ValidationError) as exc:
            return {"error": _error_message(exc)}

    return wrapper


def build_ticket_tools(service: TicketService | None = None) -> list[BaseTool]:
    """Create the IT support ticket tools, all sharing one TicketService.

    Args:
        service: TicketService to use. Defaults to TicketService(), which reads
            TICKETS_DB_PATH from the .env file.
    """
    service = service or TicketService()

    @tool
    @_returns_errors
    def register_ticket(
        raised_by: str,
        title: str,
        description: str,
        priority: PriorityValue,
        department: str,
        remarks: str | None = None,
    ) -> dict:
        """Register a new IT support ticket. It starts with status 'Open'.

        Args:
            raised_by: Name of the person reporting the issue.
            title: Short summary of the issue.
            description: Detailed description of the issue.
            priority: One of Low, Medium, High, Critical.
            department: Department of the person raising the ticket.
            remarks: Optional extra notes.
        """
        ticket = service.register_ticket(
            {
                "raised_by": raised_by,
                "title": title,
                "description": description,
                "priority": priority,
                "department": department,
                "remarks": remarks,
            }
        )
        return ticket.model_dump(mode="json")

    @tool
    @_returns_errors
    def find_tickets(
        title: str | None = None,
        description: str | None = None,
        priority: str | None = None,
        department: str | None = None,
        remarks: str | None = None,
    ) -> dict:
        """Search non-archived tickets by partial, case-insensitive filters.

        Every filter is optional; filters are combined with AND. With no filters,
        all non-archived tickets are returned.

        Args:
            title: Text contained in the title.
            description: Text contained in the description.
            priority: Text contained in the priority (Low, Medium, High, Critical).
            department: Text contained in the department.
            remarks: Text contained in the remarks.
        """
        tickets = service.find_tickets(
            title=title,
            description=description,
            priority=priority,
            department=department,
            remarks=remarks,
        )
        return {"count": len(tickets), "tickets": [t.model_dump(mode="json") for t in tickets]}

    @tool
    @_returns_errors
    def get_ticket(ticket_id: str) -> dict:
        """Get full details of a ticket by its ID (e.g. TKT-00001).
        Archived tickets are reported as not found.

        Args:
            ticket_id: The ticket ID, e.g. TKT-00001.
        """
        return service.get_ticket(ticket_id).model_dump(mode="json")

    @tool
    @_returns_errors
    def update_ticket(
        ticket_id: str,
        title: str | None = None,
        description: str | None = None,
        priority: PriorityValue | None = None,
        department: str | None = None,
        remarks: str | None = None,
        status: ActiveStatusValue | None = None,
    ) -> dict:
        """Update an Open or In Progress ticket. Only pass the fields to change.
        Status can only be set to 'Open' or 'In Progress'; use resolve_ticket
        and archive_ticket for the other statuses.

        Args:
            ticket_id: The ticket ID, e.g. TKT-00001.
            title: New title.
            description: New description.
            priority: New priority: Low, Medium, High or Critical.
            department: New department.
            remarks: New remarks.
            status: New status: 'Open' or 'In Progress'.
        """
        changes = {
            "title": title,
            "description": description,
            "priority": priority,
            "department": department,
            "remarks": remarks,
            "status": status,
        }
        changes = {field: value for field, value in changes.items() if value is not None}
        return service.update_ticket(ticket_id, changes).model_dump(mode="json")

    @tool
    @_returns_errors
    def resolve_ticket(ticket_id: str, resolved_by: str, remarks: str) -> dict:
        """Resolve an Open or In Progress ticket. Sets status to 'Resolved'.

        Args:
            ticket_id: The ticket ID, e.g. TKT-00001.
            resolved_by: Name of the person who resolved the issue.
            remarks: Resolution notes describing what was done.
        """
        payload = {"resolved_by": resolved_by, "remarks": remarks}
        return service.resolve_ticket(ticket_id, payload).model_dump(mode="json")

    @tool
    @_returns_errors
    def archive_ticket(ticket_id: str) -> dict:
        """Archive a Resolved ticket.

        Archived tickets no longer appear in searches or lookups.

        Args:
            ticket_id: The ticket ID, e.g. TKT-00001.
        """
        return service.archive_ticket(ticket_id).model_dump(mode="json")

    return [
        register_ticket,
        find_tickets,
        get_ticket,
        update_ticket,
        resolve_ticket,
        archive_ticket,
    ]
