"""Pydantic v2 schemas used to validate input and return ticket data."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from it_tickets.enums import ACTIVE_STATUSES, Priority, TicketStatus

NonEmptyStr = Field(min_length=1)


class _InputSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class TicketCreate(_InputSchema):
    """Data required to register a new ticket."""

    raised_by: str = NonEmptyStr
    title: str = NonEmptyStr
    description: str = NonEmptyStr
    priority: Priority
    department: str = NonEmptyStr
    remarks: str | None = None
    ticket_date: datetime = Field(default_factory=datetime.now)


class TicketUpdate(_InputSchema):
    """Fields that can be changed on an Open / In Progress ticket."""

    title: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    priority: Priority | None = None
    department: str | None = Field(default=None, min_length=1)
    remarks: str | None = None
    status: TicketStatus | None = None

    @field_validator("status")
    @classmethod
    def _only_active_status(cls, value: TicketStatus | None) -> TicketStatus | None:
        if value is not None and value not in ACTIVE_STATUSES:
            raise ValueError(
                "status can only be changed to 'Open' or 'In Progress'; "
                "use resolve_ticket / archive_ticket for other transitions"
            )
        return value

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "TicketUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided to update a ticket")
        return self


class TicketResolve(_InputSchema):
    """Data required to resolve a ticket."""

    resolved_by: str = NonEmptyStr
    remarks: str = NonEmptyStr


class TicketRead(BaseModel):
    """Ticket details returned to callers."""

    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    ticket_date: datetime
    raised_by: str
    title: str
    description: str
    priority: Priority
    department: str
    status: TicketStatus
    resolved_by: str | None
    remarks: str | None
