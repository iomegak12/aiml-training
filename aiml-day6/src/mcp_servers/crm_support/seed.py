"""Deterministic demo data for the CRM database.

``seed/seed_data.json`` is generated from the corpus catalog by ``scripts/build_crm_seed.py``
and shipped inside the image, so the server needs nothing else to start with realistic data.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp_servers.crm_support.db import Repository

SEED_FILE = Path(__file__).parent / "seed" / "seed_data.json"


def load_seed_file(path: Path = SEED_FILE) -> dict:
    """Read the seed JSON (``{"customers": [...], "tickets": [...]}``)."""
    return json.loads(path.read_text(encoding="utf-8"))


def seed_database(repo: Repository, *, enabled: bool, force: bool = False) -> str:
    """Seed ``repo`` when empty (or always with ``force``). Returns a status line for the banner."""
    counts = repo.counts()
    if force:
        repo.reset()
    elif counts["customers"] or counts["tickets"]:
        return "existing data kept"
    elif not enabled:
        return "seeding disabled (CRM_SEED_ON_START=false)"
    if not SEED_FILE.exists():
        return f"seed file missing: {SEED_FILE.name}"
    data = load_seed_file()
    repo.load_seed(data["customers"], data["tickets"])
    return f"seeded {len(data['customers'])} customers and {len(data['tickets'])} tickets" + (" (reset)" if force else "")
