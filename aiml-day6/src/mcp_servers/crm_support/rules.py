"""Business rules enforced by the ticket tools.

Every violation raises ``BusinessRuleError`` with a message an agent can relay to the user.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from enum import StrEnum

from mcp_servers.crm_support.models import (
    OPEN_STATUSES,
    CustomerProfile,
    SupportTicket,
    TicketPriority,
    TicketStatus,
)

DUPLICATE_SIMILARITY = 0.85


class BusinessRuleError(ValueError):
    """A request that is well-formed but not allowed by CRM business rules."""


def validate_enum(value: str | None, enum: type[StrEnum], field: str) -> str | None:
    """Normalise ``value`` to a member of ``enum`` or raise with the allowed values listed."""
    if value is None or value == "":
        return None
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    allowed = [m.value for m in enum]
    if normalized not in allowed:
        raise BusinessRuleError(f"Invalid {field} '{value}'. Allowed values: {', '.join(allowed)}.")
    return normalized


def require_active(customer: CustomerProfile | None, customer_id: str) -> CustomerProfile:
    """The customer must exist and be active to raise a ticket."""
    if customer is None:
        raise BusinessRuleError(f"Customer '{customer_id}' was not found.")
    if not customer.active_status:
        raise BusinessRuleError(
            f"Customer {customer.customer_id} ({customer.full_name}) is inactive and cannot raise tickets. "
            "Reactivate the profile through the CRM team first.")
    return customer


def require_resolvable(ticket: SupportTicket | None, ticket_id: str) -> SupportTicket:
    """Only existing tickets that are open or in progress can be resolved."""
    if ticket is None:
        raise BusinessRuleError(f"Ticket '{ticket_id}' was not found.")
    if ticket.status not in OPEN_STATUSES:
        raise BusinessRuleError(
            f"Ticket {ticket.ticket_id} is already '{ticket.status}' and cannot be resolved again "
            f"(resolved by {ticket.resolved_by or 'n/a'} on {ticket.resolution_date or 'n/a'}).")
    return ticket


def require_text(value: str | None, field: str, min_length: int = 3) -> str:
    """A mandatory free-text field must have at least ``min_length`` non-blank characters."""
    if not value or len(value.strip()) < min_length:
        raise BusinessRuleError(f"'{field}' is required (at least {min_length} characters).")
    return value.strip()


def _normalize_title(title: str) -> str:
    """Lower-case and collapse punctuation/whitespace for similarity comparison."""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def find_duplicate(title: str, open_tickets: list[SupportTicket]) -> SupportTicket | None:
    """An open ticket of the same customer whose title is near-identical (similarity >= 0.85)."""
    wanted = _normalize_title(title)
    for ticket in open_tickets:
        if ticket.status in OPEN_STATUSES and \
                SequenceMatcher(None, wanted, _normalize_title(ticket.title)).ratio() >= DUPLICATE_SIMILARITY:
            return ticket
    return None


__all__ = [
    "BusinessRuleError", "TicketPriority", "TicketStatus", "find_duplicate", "require_active",
    "require_resolvable", "require_text", "validate_enum",
]
