"""TicketService: the public API for managing IT support tickets."""

from typing import Any

from sqlalchemy import String, select, type_coerce
from sqlalchemy.orm import Session

from it_tickets.config import get_database_path
from it_tickets.database import create_session_factory
from it_tickets.enums import ACTIVE_STATUSES, TicketStatus
from it_tickets.exceptions import InvalidStatusTransitionError, TicketNotFoundError
from it_tickets.models import Ticket
from it_tickets.schemas import TicketCreate, TicketRead, TicketResolve, TicketUpdate

TICKET_ID_PREFIX = "TKT-"


class TicketService:
    """Register, find, update, resolve and archive IT support tickets.

    Args:
        database_path: SQLite database file path. If omitted, it is read from
            TICKETS_DB_PATH in the .env file / environment.
    """

    def __init__(self, database_path: str | None = None) -> None:
        self._session_factory = create_session_factory(database_path or get_database_path())

    def register_ticket(self, data: TicketCreate | dict[str, Any]) -> TicketRead:
        payload = TicketCreate.model_validate(data)
        with self._session_factory() as session, session.begin():
            ticket = Ticket(**payload.model_dump(), status=TicketStatus.OPEN)
            session.add(ticket)
            session.flush()  # assigns the auto-increment id
            ticket.ticket_id = f"{TICKET_ID_PREFIX}{ticket.id:05d}"
            return TicketRead.model_validate(ticket)

    def get_ticket(self, ticket_id: str) -> TicketRead:
        with self._session_factory() as session:
            return TicketRead.model_validate(self._get_non_archived(session, ticket_id))

    def find_tickets(
        self,
        *,
        title: str | None = None,
        description: str | None = None,
        priority: str | None = None,
        department: str | None = None,
        remarks: str | None = None,
    ) -> list[TicketRead]:
        """Find non-archived tickets.

        Each given filter is a partial, case-insensitive match; filters are AND-ed.
        With no filters, all non-archived tickets are returned.
        """
        filters = [
            (Ticket.title, title),
            (Ticket.description, description),
            (type_coerce(Ticket.priority, String), priority),  # match on the stored text value
            (Ticket.department, department),
            (Ticket.remarks, remarks),
        ]
        stmt = select(Ticket).where(Ticket.status != TicketStatus.ARCHIVED)
        for column, value in filters:
            if value is not None:
                stmt = stmt.where(column.icontains(value, autoescape=True))
        stmt = stmt.order_by(Ticket.id)

        with self._session_factory() as session:
            return [TicketRead.model_validate(t) for t in session.scalars(stmt)]

    def update_ticket(self, ticket_id: str, data: TicketUpdate | dict[str, Any]) -> TicketRead:
        payload = TicketUpdate.model_validate(data)
        with self._session_factory() as session, session.begin():
            ticket = self._get_non_archived(session, ticket_id)
            self._require_status(ticket, ACTIVE_STATUSES, "update")
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(ticket, field, value)
            return TicketRead.model_validate(ticket)

    def resolve_ticket(self, ticket_id: str, data: TicketResolve | dict[str, Any]) -> TicketRead:
        payload = TicketResolve.model_validate(data)
        with self._session_factory() as session, session.begin():
            ticket = self._get_non_archived(session, ticket_id)
            self._require_status(ticket, ACTIVE_STATUSES, "resolve")
            ticket.resolved_by = payload.resolved_by
            ticket.remarks = payload.remarks
            ticket.status = TicketStatus.RESOLVED
            return TicketRead.model_validate(ticket)

    def archive_ticket(self, ticket_id: str) -> TicketRead:
        with self._session_factory() as session, session.begin():
            ticket = self._get_non_archived(session, ticket_id)
            self._require_status(ticket, (TicketStatus.RESOLVED,), "archive")
            ticket.status = TicketStatus.ARCHIVED
            return TicketRead.model_validate(ticket)

    @staticmethod
    def _get_non_archived(session: Session, ticket_id: str) -> Ticket:
        stmt = select(Ticket).where(
            Ticket.ticket_id == ticket_id,
            Ticket.status != TicketStatus.ARCHIVED,
        )
        ticket = session.scalars(stmt).one_or_none()
        if ticket is None:
            raise TicketNotFoundError(ticket_id)
        return ticket

    @staticmethod
    def _require_status(
        ticket: Ticket, allowed: tuple[TicketStatus, ...], action: str
    ) -> None:
        if ticket.status not in allowed:
            allowed_text = " / ".join(s.value for s in allowed)
            raise InvalidStatusTransitionError(
                f"Cannot {action} ticket '{ticket.ticket_id}' with status "
                f"'{ticket.status.value}' (allowed: {allowed_text})"
            )
