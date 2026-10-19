"""Enumerations for ticket priority and status."""

from enum import Enum


class Priority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class TicketStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"
    ARCHIVED = "Archived"


# Statuses in which a ticket can still be updated or resolved.
ACTIVE_STATUSES = (TicketStatus.OPEN, TicketStatus.IN_PROGRESS)
