from datetime import datetime

import pytest

from agent_tools import LOCAL_TOOLS, build_ticket_tools, get_current_time, get_location, get_weather


@pytest.fixture
def tools(service):
    return {t.name: t for t in build_ticket_tools(service)}


@pytest.fixture
def new_ticket(tools):
    return tools["register_ticket"].invoke(
        {
            "raised_by": "Alice",
            "title": "Printer not working",
            "description": "Paper jam on floor 3",
            "priority": "High",
            "department": "Finance",
        }
    )


def _resolve(tools, ticket_id):
    return tools["resolve_ticket"].invoke(
        {"ticket_id": ticket_id, "resolved_by": "Bob", "remarks": "Cleared the jam"}
    )


# --- ticket tools ----------------------------------------------------------


def test_ticket_tool_names(tools):
    assert list(tools) == [
        "register_ticket",
        "find_tickets",
        "get_ticket",
        "update_ticket",
        "resolve_ticket",
        "archive_ticket",
    ]


def test_ticket_tools_expose_argument_schemas(tools):
    register_args = tools["register_ticket"].args
    assert set(register_args) == {"raised_by", "title", "description", "priority", "department", "remarks"}
    assert register_args["priority"]["enum"] == ["Low", "Medium", "High", "Critical"]
    assert tools["update_ticket"].args["status"]["anyOf"][0]["enum"] == ["Open", "In Progress"]
    assert "partial" in tools["find_tickets"].description


def test_default_service_uses_env_db(db_path):
    tools = {t.name: t for t in build_ticket_tools()}
    result = tools["find_tickets"].invoke({})
    assert result == {"count": 0, "tickets": []}
    assert db_path.exists()


def test_register_ticket_tool(new_ticket):
    assert new_ticket["ticket_id"] == "TKT-00001"
    assert new_ticket["status"] == "Open"
    assert new_ticket["priority"] == "High"


def test_find_tickets_tool(tools, new_ticket):
    result = tools["find_tickets"].invoke({"title": "PRINTER", "department": "fin"})
    assert result["count"] == 1
    assert result["tickets"][0]["ticket_id"] == new_ticket["ticket_id"]
    assert tools["find_tickets"].invoke({"department": "hr"})["count"] == 0


def test_get_ticket_tool(tools, new_ticket):
    assert tools["get_ticket"].invoke({"ticket_id": new_ticket["ticket_id"]}) == new_ticket


def test_update_ticket_tool_only_sends_given_fields(tools, new_ticket):
    result = tools["update_ticket"].invoke(
        {"ticket_id": new_ticket["ticket_id"], "priority": "Critical", "status": "In Progress"}
    )
    assert result["priority"] == "Critical"
    assert result["status"] == "In Progress"
    assert result["title"] == new_ticket["title"]


def test_resolve_and_archive_tools(tools, new_ticket):
    resolved = _resolve(tools, new_ticket["ticket_id"])
    assert resolved["status"] == "Resolved"
    assert resolved["resolved_by"] == "Bob"

    archived = tools["archive_ticket"].invoke({"ticket_id": new_ticket["ticket_id"]})
    assert archived["status"] == "Archived"
    assert tools["find_tickets"].invoke({})["count"] == 0


def test_not_found_returned_as_error(tools):
    result = tools["get_ticket"].invoke({"ticket_id": "TKT-99999"})
    assert result == {"error": "Ticket 'TKT-99999' not found"}


def test_invalid_transition_returned_as_error(tools, new_ticket):
    _resolve(tools, new_ticket["ticket_id"])
    result = tools["update_ticket"].invoke({"ticket_id": new_ticket["ticket_id"], "title": "x"})
    assert "Cannot update" in result["error"]


def test_archive_unresolved_returned_as_error(tools, new_ticket):
    result = tools["archive_ticket"].invoke({"ticket_id": new_ticket["ticket_id"]})
    assert "Cannot archive" in result["error"]


def test_validation_error_returned_as_error(tools, new_ticket):
    result = tools["update_ticket"].invoke({"ticket_id": new_ticket["ticket_id"]})
    assert "at least one field" in result["error"]

    result = tools["resolve_ticket"].invoke(
        {"ticket_id": new_ticket["ticket_id"], "resolved_by": " ", "remarks": "done"}
    )
    assert "resolved_by" in result["error"]


# --- local tools -----------------------------------------------------------


def test_local_tool_names():
    assert [t.name for t in LOCAL_TOOLS] == ["get_location", "get_weather", "get_current_time"]


def test_get_location():
    location = get_location.invoke({})
    assert location["city"] == "Bengaluru"
    assert location["timezone"] == "Asia/Kolkata"


@pytest.mark.parametrize(("city", "condition"), [("Tokyo", "Sunny"), ("  LONDON ", "Overcast")])
def test_get_weather_known_city(city, condition):
    assert get_weather.invoke({"city": city})["condition"] == condition


def test_get_weather_unknown_city_uses_default():
    weather = get_weather.invoke({"city": "Atlantis"})
    assert weather["city"] == "Atlantis"
    assert weather["condition"] == "Mild and clear"


def test_get_current_time_is_real():
    result = get_current_time.invoke({"timezone": "Asia/Tokyo"})
    parsed = datetime.fromisoformat(result["iso"])
    assert parsed.utcoffset().total_seconds() == 9 * 3600
    assert abs((datetime.now(parsed.tzinfo) - parsed).total_seconds()) < 60


def test_get_current_time_default_timezone():
    assert get_current_time.invoke({})["timezone"] == "Asia/Kolkata"


@pytest.mark.parametrize("timezone", ["Mars/Olympus", "../etc"])
def test_get_current_time_invalid_timezone(timezone):
    assert "Unknown timezone" in get_current_time.invoke({"timezone": timezone})["error"]
