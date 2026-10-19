"""it_tickets: a small library for tracking IT support tickets in SQLite."""

from it_tickets.enums import Priority, TicketStatus
from it_tickets.exceptions import (
    ConfigurationError,
    InvalidStatusTransitionError,
    TicketError,
    TicketNotFoundError,
)
from it_tickets.schemas import TicketCreate, TicketRead, TicketResolve, TicketUpdate
from it_tickets.service import TicketService

__all__ = [
    "ConfigurationError",
    "InvalidStatusTransitionError",
    "Priority",
    "TicketCreate",
    "TicketError",
    "TicketNotFoundError",
    "TicketRead",
    "TicketResolve",
    "TicketService",
    "TicketStatus",
    "TicketUpdate",
]
