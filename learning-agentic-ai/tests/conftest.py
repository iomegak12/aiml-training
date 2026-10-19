import pytest

from it_tickets import TicketService


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "tickets.db"
    monkeypatch.setenv("TICKETS_DB_PATH", str(path))
    return path


@pytest.fixture
def service(db_path):
    return TicketService()


@pytest.fixture
def ticket_data():
    return {
        "raised_by": "Alice",
        "title": "Printer not working",
        "description": "The 3rd floor printer shows a paper jam error",
        "priority": "High",
        "department": "Finance",
    }
