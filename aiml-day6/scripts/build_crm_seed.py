"""Generate the CRM/support seed data from the corpus catalog (deterministic).

Writes ``src/mcp_servers/crm_support/seed/seed_data.json``: fictional customers and
support tickets that reference the real products and error codes of the corpus, so
agentic demos can hop from a CRM ticket to the matching product manual.

A few *anchor* customers have fixed stories used by the notebooks:

    CUST-0001  Ananya Iyer   active,   Voltara Lumina 55 Pro, open high ticket for error E-715
    CUST-0002  Rohan Mehta   INACTIVE (cannot raise tickets)
    CUST-0003  Kavya Reddy   active,   Nexora Aria 12, resolved eSIM ticket
    CUST-0004  Arjun Nair    active,   Lumenix OLED O65, open critical LX-90 ticket
    CUST-0005  Priya Sharma  active,   Zentrix Z5, open slow-charging ticket (10 W charger in box)

Usage:
    uv run scripts/build_crm_seed.py
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data_generation.catalog import PHONES, TVS

OUT = Path(__file__).resolve().parents[1] / "src" / "mcp_servers" / "crm_support" / "seed" / "seed_data.json"
RNG = random.Random(20261019)

FIRST = ["Aditya", "Aisha", "Akash", "Anjali", "Deepak", "Divya", "Farhan", "Gauri", "Harish", "Isha", "Karan",
         "Lakshmi", "Manoj", "Meena", "Nikhil", "Neha", "Pooja", "Rajesh", "Ritu", "Sameer", "Shreya", "Siddharth",
         "Sunita", "Tanvi", "Varun", "Yamini", "Zoya", "Gaurav", "Sneha", "Vivek", "Amit", "Bhavna", "Chirag",
         "Esha", "Hemant"]
LAST = ["Agarwal", "Bose", "Chatterjee", "Desai", "Fernandes", "Ghosh", "Gupta", "Iyer", "Joshi", "Kapoor", "Khan",
        "Kulkarni", "Menon", "Mishra", "Nair", "Patel", "Pillai", "Rao", "Saxena", "Shetty", "Singh", "Thomas",
        "Verma", "Yadav"]
CITIES = [("Bengaluru", "Karnataka", "5600"), ("Mumbai", "Maharashtra", "4000"), ("Chennai", "Tamil Nadu", "6000"),
          ("Hyderabad", "Telangana", "5000"), ("Pune", "Maharashtra", "4110"), ("Kolkata", "West Bengal", "7000"),
          ("New Delhi", "Delhi", "1100"), ("Ahmedabad", "Gujarat", "3800"), ("Kochi", "Kerala", "6820"),
          ("Jaipur", "Rajasthan", "3020"), ("Lucknow", "Uttar Pradesh", "2260"), ("Coimbatore", "Tamil Nadu", "6410")]
BUILDINGS = ["Lakeview Residency", "Palm Grove Apartments", "Sunrise Enclave", "Green Meadows", "Silver Oak Towers",
             "Lotus Heights", "Riverside Homes", "Banyan Court", "Orchid Gardens", "Maple Residency"]
STREETS = ["MG Road", "Station Road", "Temple Street", "Park Avenue", "Ring Road", "Gandhi Nagar Main Road",
           "Nehru Street", "Lake Road", "College Road", "Market Street"]
REMARKS = ["Prefers WhatsApp updates.", "Corporate account - invoices to accounts team.", "Prefers email communication.",
           "Senior citizen - schedule home visits before noon.", "Loyalty programme gold member.",
           "Requested callback in Hindi.", None, None, None]
AGENTS = ["Meera Krishnan (L2 Support)", "Vikram Joshi (Field Service)", "Sana Qureshi (L1 Support)",
          "Rahul Verma (Product Specialist)"]

PHONE_ISSUES = [
    ("Battery drains quickly", "Battery drops from 100% to 20% in about six hours with light use.",
     "Enabled Battery Saver and Charging Protection; removed a misbehaving app. Battery life back to normal."),
    ("Slow charging with supplied adapter", "Charging takes more than three hours with the adapter from the box.",
     "Explained adapter wattage versus maximum supported charging; cleaned the USB-C port. Charging time normal."),
    ("Fingerprint sensor not recognising finger", "Fingerprint unlock fails most of the time since last week.",
     "Re-registered fingerprints after cleaning the sensor; recognition reliable."),
    ("Phone overheating while charging", "Phone becomes very warm while fast charging inside its case.",
     "Advised charging without the case; verified temperature within limits after software update."),
    ("Blurry camera photos", "Photos from the main camera look hazy, especially indoors.",
     "Lens cleaned and camera app cache cleared; photos sharp again."),
    ("No network signal after update", "Shows 'Emergency calls only' since the latest software update.",
     "Reset APN settings and re-seated the SIM tray; network restored."),
]
TV_ISSUES = [
    ("No sound from TV speakers", "Picture is fine but the TV speakers are silent.",
     "Sound Output was set to an external device; switched back to TV Speaker."),
    ("Wi-Fi keeps disconnecting", "The TV drops the Wi-Fi connection several times every evening.",
     "Moved to the 5 GHz band and updated the TV software; connection stable."),
    ("Remote does not respond", "Voice remote stopped working even with new batteries.",
     "Re-paired the remote by holding Home and Back for 5 seconds."),
    ("Wall-mount installation request", "Customer requests professional wall mounting for the new TV.",
     "Installation completed by authorised technician with the correct VESA bracket."),
]


def ts(dt: datetime) -> str:
    """ISO-8601 UTC timestamp with Z suffix."""
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_customer(n: int, full_name: str, active: bool = True, remarks: str | None = None,
                  city_index: int | None = None) -> dict:
    """One fictional customer profile with consistent placeholder contact details."""
    city, state, pin_prefix = CITIES[city_index if city_index is not None else RNG.randrange(len(CITIES))]
    first, last = full_name.lower().split()[0], full_name.lower().split()[-1]
    created = datetime(2025, 6, 1, tzinfo=timezone.utc) + timedelta(days=RNG.randrange(330), hours=RNG.randrange(24))
    return {
        "customer_id": f"CUST-{n:04d}",
        "full_name": full_name,
        "communication_address": f"{RNG.randrange(1, 400)}, {RNG.choice(BUILDINGS)}, {RNG.choice(STREETS)}, "
                                 f"{city}, {state} {pin_prefix}{RNG.randrange(10, 99)}",
        "email": f"{first}.{last}{n}@mail.example",
        "phone_number": f"+91 00000 {RNG.randrange(10000, 99999)}",
        "credit_limit": float(RNG.choice([25000, 50000, 75000, 100000, 150000, 200000, 300000])),
        "active_status": active,
        "remarks": remarks if remarks is not None else RNG.choice(REMARKS),
        "created_at": ts(created),
        "updated_at": ts(created),
    }


def make_ticket(customer: dict, title: str, description: str, product: str | None, status: str, priority: str,
                created: datetime, resolution: str | None = None) -> dict:
    """One ticket; resolved/closed tickets get a resolver, date and remarks."""
    done = status in ("resolved", "closed")
    resolved_at = created + timedelta(days=RNG.randrange(1, 10), hours=RNG.randrange(8)) if done else None
    return {
        "ticket_id": "",  # assigned after sorting by creation time
        "title": title,
        "description": description,
        "raised_by": customer["customer_id"],
        "product_model": product,
        "status": status,
        "priority": priority,
        "resolved_by": RNG.choice(AGENTS) if done else None,
        "resolution_date": ts(resolved_at) if done else None,
        "resolution_remarks": resolution if done else None,
        "created_at": ts(created),
        "updated_at": ts(resolved_at or created),
    }


def random_issue(product: dict) -> tuple[str, str, str, str]:
    """A plausible (title, description, resolution, product_model) for a product from the catalog."""
    name = f"{product['brand']} {product['model']}"
    if product in TVS and RNG.random() < 0.6:
        code, meaning, action = RNG.choice(product["error_codes"])
        return (f"{product['model']} shows error {code}",
                f"The customer's {name} displays error {code}: {meaning}", action, product["model"])
    title, desc, fix = RNG.choice(TV_ISSUES if product in TVS else PHONE_ISSUES)
    return f"{title} ({product['model']})", f"{desc} Product: {name}.", fix, product["model"]


def build() -> dict:
    """Build the full deterministic seed: anchors first, then random customers and tickets."""
    customers = [
        make_customer(1, "Ananya Iyer", remarks="Owns Voltara Lumina 55 Pro (VT-55L7Q) bought March 2026; "
                                                "prefers email updates.", city_index=0),
        make_customer(2, "Rohan Mehta", active=False, remarks="Account inactive since August 2026 - pending KYC "
                                                               "re-verification.", city_index=1),
        make_customer(3, "Kavya Reddy", remarks="Owns Nexora Aria 12; uses eSIM.", city_index=3),
        make_customer(4, "Arjun Nair", remarks="Owns Lumenix OLED O65; home theatre enthusiast.", city_index=8),
        make_customer(5, "Priya Sharma", remarks="Owns Zentrix Z5; price-sensitive buyer.", city_index=6),
    ]
    used = {c["full_name"] for c in customers}
    while len(customers) < 40:
        name = f"{RNG.choice(FIRST)} {RNG.choice(LAST)}"
        if name not in used:
            used.add(name)
            customers.append(make_customer(len(customers) + 1, name, active=RNG.random() > 0.1))

    day = datetime(2026, 1, 5, 9, tzinfo=timezone.utc)
    c = {x["customer_id"]: x for x in customers}
    tickets = [
        make_ticket(c["CUST-0001"], "Lumina 55 Pro shows error E-715 with game console",
                    "The Voltara Lumina 55 Pro shows error E-715 (HDMI 2.1 FRL link training failed) when the "
                    "PS5 is connected at 4K 120 Hz. Picture drops every few minutes.", "Lumina 55 Pro", "open", "high",
                    datetime(2026, 10, 14, 11, tzinfo=timezone.utc)),
        make_ticket(c["CUST-0001"], "Remote not pairing after battery change",
                    "Voltara SmartGlide remote stopped working after the customer replaced the batteries.",
                    "Lumina 55 Pro", "resolved", "low", datetime(2026, 4, 2, 15, tzinfo=timezone.utc),
                    "Re-paired the remote by holding Home and Back for 5 seconds."),
        make_ticket(c["CUST-0002"], "Lumina 43 picture has dark corners",
                    "Uneven brightness in dark scenes on the Voltara Lumina 43.", "Lumina 43", "closed", "low",
                    datetime(2026, 2, 11, 10, tzinfo=timezone.utc),
                    "Explained LED backlight characteristics; reduced Backlight setting."),
        make_ticket(c["CUST-0003"], "eSIM activation fails on Aria 12",
                    "The Nexora Aria 12 shows an error while scanning the operator's eSIM QR code.", "Aria 12",
                    "resolved", "medium", datetime(2026, 7, 20, 13, tzinfo=timezone.utc),
                    "QR code had expired; customer obtained a new code and activated the eSIM over Wi-Fi."),
        make_ticket(c["CUST-0004"], "OLED O65 shows LX-90 pixel refresh interrupted",
                    "The Lumenix OLED O65 shows error LX-90 every morning; faint ghost images of news tickers.",
                    "OLED O65", "open", "critical", datetime(2026, 10, 16, 8, tzinfo=timezone.utc)),
        make_ticket(c["CUST-0004"], "Soundbar has no sound over HDMI eARC",
                    "Soundbar connected to the Lumenix OLED O65 produces no audio.", "OLED O65", "in_progress", "medium",
                    datetime(2026, 9, 28, 18, tzinfo=timezone.utc)),
        make_ticket(c["CUST-0005"], "Zentrix Z5 charges very slowly",
                    "The Zentrix Z5 takes over three hours to charge with the adapter from the box.", "Z5", "open",
                    "medium", datetime(2026, 10, 10, 12, tzinfo=timezone.utc)),
    ]

    products = TVS + PHONES
    open_titles = {(t["raised_by"], t["title"]) for t in tickets}
    while len(tickets) < 120:
        customer = RNG.choice(customers[5:])
        title, description, fix, model = random_issue(RNG.choice(products))
        status = RNG.choices(["open", "in_progress", "resolved", "closed"], weights=[3, 2, 4, 1])[0]
        if (customer["customer_id"], title) in open_titles:
            continue
        open_titles.add((customer["customer_id"], title))
        priority = RNG.choices(["low", "medium", "high", "critical"], weights=[2, 4, 3, 1])[0]
        created = day + timedelta(days=RNG.randrange(275), hours=RNG.randrange(10))
        joined = datetime.fromisoformat(customer["created_at"].replace("Z", "+00:00"))
        created = max(created, joined + timedelta(days=RNG.randrange(1, 30)))  # never before the customer existed
        tickets.append(make_ticket(customer, title, description, model, status, priority, created, fix))

    tickets.sort(key=lambda t: (t["created_at"], t["raised_by"], t["title"]))
    for i, ticket in enumerate(tickets, start=1):
        ticket["ticket_id"] = f"TKT-{i:06d}"
    return {"generated_by": "scripts/build_crm_seed.py", "customers": customers, "tickets": tickets}


def main() -> int:
    """Write the seed JSON and print a summary."""
    data = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    statuses = {s: sum(t["status"] == s for t in data["tickets"]) for s in ("open", "in_progress", "resolved", "closed")}
    print(f"Wrote {OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT}: "
          f"{len(data['customers'])} customers, {len(data['tickets'])} tickets {statuses}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
