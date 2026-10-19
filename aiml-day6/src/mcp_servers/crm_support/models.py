"""Pydantic models and enums shared by the repository, tools and resources."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class TicketStatus(StrEnum):
    """Lifecycle of a support ticket."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    """Business priority of a support ticket."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


OPEN_STATUSES = (TicketStatus.OPEN, TicketStatus.IN_PROGRESS)


class CustomerProfile(BaseModel):
    """A customer profile as stored in the CRM."""

    customer_id: str = Field(description="Profile ID, e.g. CUST-0001")
    full_name: str
    communication_address: str
    email: str
    phone_number: str
    credit_limit: float = Field(description="Credit limit in INR")
    active_status: bool
    remarks: str | None = None
    created_at: str
    updated_at: str


class SupportTicket(BaseModel):
    """A support ticket raised by a customer."""

    ticket_id: str = Field(description="Ticket ID, e.g. TKT-000001")
    title: str
    description: str
    raised_by: str = Field(description="customer_id of the customer who raised the ticket")
    product_model: str | None = Field(default=None, description="Product the ticket is about, e.g. 'Lumina 55 Pro'")
    status: TicketStatus
    priority: TicketPriority
    resolved_by: str | None = None
    resolution_date: str | None = None
    resolution_remarks: str | None = None
    created_at: str
    updated_at: str


class CustomerSearchResult(BaseModel):
    """A page of customer search results."""

    total: int = Field(description="Number of matching customers")
    count: int = Field(description="Number of customers in this page")
    customers: list[CustomerProfile]


class TicketSearchResult(BaseModel):
    """A page of ticket search results."""

    total: int = Field(description="Number of matching tickets")
    count: int = Field(description="Number of tickets in this page")
    tickets: list[SupportTicket]


class RegisterTicketResult(BaseModel):
    """Outcome of ``register_ticket``: a new ticket, or the existing duplicate."""

    created: bool
    message: str
    ticket: SupportTicket
