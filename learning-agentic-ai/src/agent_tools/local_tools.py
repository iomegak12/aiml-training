"""Local utility tools. Weather and location return dummy data for demonstration;
the current time is real."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool

DUMMY_LOCATION = {
    "city": "Bengaluru",
    "region": "Karnataka",
    "country": "India",
    "timezone": "Asia/Kolkata",
    "latitude": 12.9716,
    "longitude": 77.5946,
}

DUMMY_WEATHER = {
    "bengaluru": {"condition": "Partly cloudy", "temperature_c": 27, "humidity_pct": 64, "wind_kph": 12},
    "chennai": {"condition": "Humid and sunny", "temperature_c": 33, "humidity_pct": 78, "wind_kph": 15},
    "mumbai": {"condition": "Light rain", "temperature_c": 29, "humidity_pct": 85, "wind_kph": 18},
    "new delhi": {"condition": "Hazy", "temperature_c": 31, "humidity_pct": 40, "wind_kph": 8},
    "london": {"condition": "Overcast", "temperature_c": 14, "humidity_pct": 72, "wind_kph": 20},
    "new york": {"condition": "Clear", "temperature_c": 18, "humidity_pct": 55, "wind_kph": 14},
    "tokyo": {"condition": "Sunny", "temperature_c": 22, "humidity_pct": 50, "wind_kph": 10},
}

DEFAULT_WEATHER = {"condition": "Mild and clear", "temperature_c": 24, "humidity_pct": 60, "wind_kph": 10}


@tool
def get_location() -> dict:
    """Get the user's current location (city, region, country, timezone, coordinates)."""
    return dict(DUMMY_LOCATION)


@tool
def get_weather(city: str) -> dict:
    """Get the current weather for a city.

    Args:
        city: City name, e.g. 'Bengaluru' or 'London'.
    """
    weather = DUMMY_WEATHER.get(city.strip().lower(), DEFAULT_WEATHER)
    return {"city": city, **weather, "note": "dummy data for demonstration"}


@tool
def get_current_time(timezone: str = "Asia/Kolkata") -> dict:
    """Get the current date and time in a timezone.

    Args:
        timezone: IANA timezone name, e.g. 'Asia/Kolkata', 'Europe/London', 'Asia/Tokyo'.
    """
    try:
        now = datetime.now(ZoneInfo(timezone))
    except (ZoneInfoNotFoundError, ValueError):
        return {"error": f"Unknown timezone '{timezone}'. Use an IANA name such as 'Asia/Kolkata'."}
    return {
        "timezone": timezone,
        "iso": now.isoformat(timespec="seconds"),
        "readable": now.strftime("%A, %d %B %Y, %I:%M %p %Z"),
    }


LOCAL_TOOLS = [get_location, get_weather, get_current_time]
