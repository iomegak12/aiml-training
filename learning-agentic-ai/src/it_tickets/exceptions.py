"""Custom exceptions raised by the it_tickets library."""


class TicketError(Exception):
    """Base class for all it_tickets errors."""


class ConfigurationError(TicketError):
    """Raised when required configuration (e.g. the database path) is missing."""


class TicketNotFoundError(TicketError):
    """Raised when a ticket does not exist or is archived."""

    def __init__(self, ticket_id: str) -> None:
        self.ticket_id = ticket_id
        super().__init__(f"Ticket '{ticket_id}' not found")


class InvalidStatusTransitionError(TicketError):
    """Raised when an operation is not allowed for the ticket's current status."""
