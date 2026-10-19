"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from it_tickets.enums import Priority, TicketStatus


class Base(DeclarativeBase):
    pass


def _enum_column(enum_cls: type) -> Enum:
    # Store the human-readable values ("In Progress") rather than member names.
    return Enum(
        enum_cls,
        native_enum=False,
        values_callable=lambda members: [m.value for m in members],
        length=20,
    )


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    ticket_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raised_by: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[Priority] = mapped_column(_enum_column(Priority), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        _enum_column(TicketStatus), nullable=False, default=TicketStatus.OPEN
    )
    resolved_by: Mapped[str | None] = mapped_column(String(100))
    remarks: Mapped[str | None] = mapped_column(Text)
