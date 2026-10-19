from datetime import datetime

import pytest
from pydantic import ValidationError

from it_tickets import (
    ConfigurationError,
    InvalidStatusTransitionError,
    Priority,
    TicketCreate,
    TicketNotFoundError,
    TicketService,
    TicketStatus,
)
from it_tickets import config


# --- configuration ---------------------------------------------------------


def test_missing_database_path_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("TICKETS_DB_PATH", raising=False)
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: None)  # ignore any local .env
    with pytest.raises(ConfigurationError):
        TicketService()


def test_database_path_from_env_creates_db_file(service, db_path):
    assert db_path.exists()


# --- register --------------------------------------------------------------


def test_register_ticket_defaults(service, ticket_data):
    before = datetime.now()
    ticket = service.register_ticket(ticket_data)

    assert ticket.ticket_id == "TKT-00001"
    assert ticket.status == TicketStatus.OPEN
    assert ticket.priority == Priority.HIGH
    assert ticket.resolved_by is None
    assert ticket.remarks is None
    assert before <= ticket.ticket_date <= datetime.now()


def test_register_ticket_ids_increment(service, ticket_data):
    first = service.register_ticket(ticket_data)
    second = service.register_ticket(TicketCreate(**ticket_data))
    assert (first.ticket_id, second.ticket_id) == ("TKT-00001", "TKT-00002")


def test_register_ticket_with_overridden_date(service, ticket_data):
    date = datetime(2026, 1, 15, 9, 30)
    ticket = service.register_ticket({**ticket_data, "ticket_date": date})
    assert ticket.ticket_date == date


@pytest.mark.parametrize(
    "override",
    [
        {"priority": "Urgent"},
        {"title": ""},
        {"title": "   "},
        {"department": None},
        {"unknown_field": "x"},
    ],
)
def test_register_ticket_validation_errors(service, ticket_data, override):
    with pytest.raises(ValidationError):
        service.register_ticket({**ticket_data, **override})


def test_register_ticket_missing_required_field(service, ticket_data):
    del ticket_data["raised_by"]
    with pytest.raises(ValidationError):
        service.register_ticket(ticket_data)


# --- get -------------------------------------------------------------------


def test_get_ticket(service, ticket_data):
    created = service.register_ticket(ticket_data)
    assert service.get_ticket(created.ticket_id) == created


def test_get_unknown_ticket_raises(service):
    with pytest.raises(TicketNotFoundError):
        service.get_ticket("TKT-99999")


def test_get_archived_ticket_raises(service, ticket_data):
    ticket = service.register_ticket(ticket_data)
    service.resolve_ticket(ticket.ticket_id, {"resolved_by": "Bob", "remarks": "Fixed"})
    service.archive_ticket(ticket.ticket_id)
    with pytest.raises(TicketNotFoundError):
        service.get_ticket(ticket.ticket_id)


# --- find ------------------------------------------------------------------


@pytest.fixture
def seeded(service):
    rows = [
        ("Printer not working", "Paper jam on floor 3", "High", "Finance", "Check tray"),
        ("VPN disconnects", "VPN drops every hour", "Critical", "Engineering", None),
        ("New laptop request", "Laptop for new joiner", "Low", "HR", "Approved by manager"),
        ("Printer toner low", "Replace toner", "Medium", "HR", None),
    ]
    return [
        service.register_ticket(
            {
                "raised_by": "Alice",
                "title": title,
                "description": desc,
                "priority": prio,
                "department": dept,
                "remarks": remarks,
            }
        )
        for title, desc, prio, dept, remarks in rows
    ]


def _titles(tickets):
    return [t.title for t in tickets]


def test_find_without_filters_returns_all_non_archived(service, seeded):
    assert len(service.find_tickets()) == 4


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"title": "PRINTER"}, ["Printer not working", "Printer toner low"]),
        ({"description": "vpn drops"}, ["VPN disconnects"]),
        ({"priority": "crit"}, ["VPN disconnects"]),
        ({"priority": "high"}, ["Printer not working"]),
        ({"department": "hr"}, ["New laptop request", "Printer toner low"]),
        ({"remarks": "MANAGER"}, ["New laptop request"]),
    ],
)
def test_find_partial_case_insensitive(service, seeded, kwargs, expected):
    assert _titles(service.find_tickets(**kwargs)) == expected


def test_find_filters_are_anded(service, seeded):
    result = service.find_tickets(title="printer", department="hr")
    assert _titles(result) == ["Printer toner low"]


def test_find_wildcard_characters_are_literal(service, seeded):
    assert service.find_tickets(title="%") == []
    assert service.find_tickets(title="_") == []


def test_find_excludes_archived_but_includes_resolved(service, seeded):
    resolved, archived = seeded[0], seeded[3]
    service.resolve_ticket(resolved.ticket_id, {"resolved_by": "Bob", "remarks": "Cleared jam"})
    service.resolve_ticket(archived.ticket_id, {"resolved_by": "Bob", "remarks": "Replaced"})
    service.archive_ticket(archived.ticket_id)

    result = service.find_tickets(title="printer")
    assert _titles(result) == ["Printer not working"]
    assert result[0].status == TicketStatus.RESOLVED


# --- update ----------------------------------------------------------------


def test_update_ticket_fields(service, ticket_data):
    ticket = service.register_ticket(ticket_data)
    updated = service.update_ticket(
        ticket.ticket_id,
        {"title": "Printer jammed", "priority": "Critical", "remarks": "Escalated"},
    )
    assert updated.title == "Printer jammed"
    assert updated.priority == Priority.CRITICAL
    assert updated.remarks == "Escalated"
    assert updated.description == ticket.description  # untouched fields kept
    assert service.get_ticket(ticket.ticket_id) == updated


def test_update_status_open_in_progress_round_trip(service, ticket_data):
    ticket = service.register_ticket(ticket_data)
    in_progress = service.update_ticket(ticket.ticket_id, {"status": "In Progress"})
    assert in_progress.status == TicketStatus.IN_PROGRESS
    reopened = service.update_ticket(ticket.ticket_id, {"status": "Open"})
    assert reopened.status == TicketStatus.OPEN


@pytest.mark.parametrize("status", ["Resolved", "Archived"])
def test_update_cannot_set_resolved_or_archived(service, ticket_data, status):
    ticket = service.register_ticket(ticket_data)
    with pytest.raises(ValidationError):
        service.update_ticket(ticket.ticket_id, {"status": status})


def test_update_requires_at_least_one_field(service, ticket_data):
    ticket = service.register_ticket(ticket_data)
    with pytest.raises(ValidationError):
        service.update_ticket(ticket.ticket_id, {})


def test_update_cannot_change_protected_fields(service, ticket_data):
    ticket = service.register_ticket(ticket_data)
    with pytest.raises(ValidationError):
        service.update_ticket(ticket.ticket_id, {"raised_by": "Mallory"})


def test_update_resolved_ticket_rejected(service, ticket_data):
    ticket = service.register_ticket(ticket_data)
    service.resolve_ticket(ticket.ticket_id, {"resolved_by": "Bob", "remarks": "Fixed"})
    with pytest.raises(InvalidStatusTransitionError):
        service.update_ticket(ticket.ticket_id, {"title": "Changed"})


def test_update_archived_ticket_rejected(service, ticket_data):
    ticket = service.register_ticket(ticket_data)
    service.resolve_ticket(ticket.ticket_id, {"resolved_by": "Bob", "remarks": "Fixed"})
    service.archive_ticket(ticket.ticket_id)
    with pytest.raises(TicketNotFoundError):
        service.update_ticket(ticket.ticket_id, {"title": "Changed"})


def test_update_unknown_ticket_raises(service):
    with pytest.raises(TicketNotFoundError):
        service.update_ticket("TKT-99999", {"title": "x"})


# --- resolve ---------------------------------------------------------------


@pytest.mark.parametrize("start_status", ["Open", "In Progress"])
def test_resolve_from_active_status(service, ticket_data, start_status):
    ticket = service.register_ticket(ticket_data)
    if start_status == "In Progress":
        service.update_ticket(ticket.ticket_id, {"status": start_status})

    resolved = service.resolve_ticket(
        ticket.ticket_id, {"resolved_by": "Bob", "remarks": "Replaced the fuser"}
    )
    assert resolved.status == TicketStatus.RESOLVED
    assert resolved.resolved_by == "Bob"
    assert resolved.remarks == "Replaced the fuser"


@pytest.mark.parametrize(
    "payload",
    [
        {"resolved_by": "Bob"},
        {"remarks": "Fixed"},
        {"resolved_by": "", "remarks": "Fixed"},
        {"resolved_by": "Bob", "remarks": "  "},
    ],
)
def test_resolve_requires_resolved_by_and_remarks(service, ticket_data, payload):
    ticket = service.register_ticket(ticket_data)
    with pytest.raises(ValidationError):
        service.resolve_ticket(ticket.ticket_id, payload)


def test_resolve_already_resolved_rejected(service, ticket_data):
    ticket = service.register_ticket(ticket_data)
    service.resolve_ticket(ticket.ticket_id, {"resolved_by": "Bob", "remarks": "Fixed"})
    with pytest.raises(InvalidStatusTransitionError):
        service.resolve_ticket(ticket.ticket_id, {"resolved_by": "Bob", "remarks": "Again"})


# --- archive ---------------------------------------------------------------


def test_archive_resolved_ticket(service, ticket_data):
    ticket = service.register_ticket(ticket_data)
    service.resolve_ticket(ticket.ticket_id, {"resolved_by": "Bob", "remarks": "Fixed"})
    archived = service.archive_ticket(ticket.ticket_id)
    assert archived.status == TicketStatus.ARCHIVED


@pytest.mark.parametrize("start_status", ["Open", "In Progress"])
def test_archive_requires_resolved(service, ticket_data, start_status):
    ticket = service.register_ticket(ticket_data)
    if start_status == "In Progress":
        service.update_ticket(ticket.ticket_id, {"status": start_status})
    with pytest.raises(InvalidStatusTransitionError):
        service.archive_ticket(ticket.ticket_id)


def test_archive_already_archived_raises_not_found(service, ticket_data):
    ticket = service.register_ticket(ticket_data)
    service.resolve_ticket(ticket.ticket_id, {"resolved_by": "Bob", "remarks": "Fixed"})
    service.archive_ticket(ticket.ticket_id)
    with pytest.raises(TicketNotFoundError):
        service.archive_ticket(ticket.ticket_id)


def test_data_persists_across_service_instances(db_path, ticket_data):
    ticket = TicketService(str(db_path)).register_ticket(ticket_data)
    assert TicketService(str(db_path)).get_ticket(ticket.ticket_id) == ticket
