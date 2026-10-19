"""SQLite repository for customer profiles and support tickets.

* One short-lived connection per operation (FastMCP runs sync tools in worker threads).
* Only parameterised SQL; user text never becomes part of a statement.
* Text filters are case-insensitive *partial* matches (``LIKE ? ESCAPE '\\'`` with
  ``%``/``_`` in user input escaped), so "kumar" finds "Ravi Kumar".
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from mcp_servers.crm_support.models import CustomerProfile, SupportTicket

MAX_LIMIT = 100
DEFAULT_LIMIT = 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id           TEXT PRIMARY KEY,
    full_name             TEXT NOT NULL,
    communication_address TEXT NOT NULL,
    email                 TEXT NOT NULL,
    phone_number          TEXT NOT NULL,
    credit_limit          REAL NOT NULL CHECK (credit_limit >= 0),
    active_status         INTEGER NOT NULL CHECK (active_status IN (0, 1)),
    remarks               TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id          TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    description        TEXT NOT NULL,
    raised_by          TEXT NOT NULL REFERENCES customers(customer_id),
    product_model      TEXT,
    status             TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    priority           TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    resolved_by        TEXT,
    resolution_date    TEXT,
    resolution_remarks TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_customers_name   ON customers(full_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_customers_email  ON customers(email COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_tickets_raised   ON tickets(raised_by);
CREATE INDEX IF NOT EXISTS ix_tickets_status   ON tickets(status, priority);
CREATE INDEX IF NOT EXISTS ix_tickets_model    ON tickets(product_model COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_tickets_created  ON tickets(created_at);
"""


def utc_now() -> str:
    """Current UTC time as an ISO-8601 string with a ``Z`` suffix (second precision)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def like_pattern(text: str) -> str:
    """Escape LIKE wildcards in user text and wrap it for a partial match."""
    escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


STOPWORDS = frozenset("a an and are as at by for from has have in is it of on or the to was with".split())


def search_words(text: str) -> list[str]:
    """Words of a free-text query that must all appear (stopwords dropped), e.g. "the slow charging" -> slow, charging."""
    words = [w for w in text.split() if w.lower() not in STOPWORDS]
    return words or [text.strip()]


def model_variants(value: str, known_models: list[str]) -> list[str]:
    """The model as given plus any known model it ends with ("Zentrix Z9 Plus" -> "Z9 Plus", a brand prefix)."""
    value = value.strip()
    suffixes = [m for m in known_models if value.lower().endswith(" " + m.lower())]
    return [value, *suffixes]


def clamp_limit(limit: int | None) -> int:
    """Bound a page size to ``1..MAX_LIMIT`` (default ``DEFAULT_LIMIT``)."""
    return max(1, min(MAX_LIMIT, limit or DEFAULT_LIMIT))


def _customer(row: sqlite3.Row) -> CustomerProfile:
    """Convert a ``customers`` row into a model."""
    data = dict(row)
    data["active_status"] = bool(data["active_status"])
    return CustomerProfile(**data)


def _ticket(row: sqlite3.Row) -> SupportTicket:
    """Convert a ``tickets`` row into a model."""
    return SupportTicket(**dict(row))


class Repository:
    """Data access for customers and tickets backed by one SQLite file."""

    def __init__(self, db_path: Path):
        """Remember the database location; call ``initialize`` before use."""
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Open a connection with foreign keys on and row access by column name; commit on success."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        """Create the database folder, schema and indexes (idempotent).

        The default rollback journal is kept on purpose: WAL needs shared memory, which is
        unreliable on Docker Desktop bind mounts (Windows/macOS) where the database lives.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def counts(self) -> dict[str, int]:
        """Number of customers and tickets."""
        with self.connect() as conn:
            return {
                "customers": conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
                "tickets": conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0],
            }

    # -- customers -----------------------------------------------------------------

    def get_customer(self, customer_id: str) -> CustomerProfile | None:
        """Fetch one customer by ID (case-insensitive), or ``None``."""
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM customers WHERE customer_id = ? COLLATE NOCASE",
                               (customer_id.strip(),)).fetchone()
        return _customer(row) if row else None

    def search_customers(self, *, name=None, email=None, phone=None, address=None, active_status=None,
                         min_credit=None, max_credit=None, limit=None, offset=0) -> tuple[int, list[CustomerProfile]]:
        """Filter customers; text filters are case-insensitive partial matches. Returns ``(total, page)``."""
        where, args = [], []
        for column, value in (("full_name", name), ("email", email), ("phone_number", phone),
                              ("communication_address", address)):
            if value:
                where.append(f"{column} LIKE ? ESCAPE '\\' COLLATE NOCASE")
                args.append(like_pattern(value))
        if active_status is not None:
            where.append("active_status = ?")
            args.append(int(active_status))
        if min_credit is not None:
            where.append("credit_limit >= ?")
            args.append(min_credit)
        if max_credit is not None:
            where.append("credit_limit <= ?")
            args.append(max_credit)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM customers {clause}", args).fetchone()[0]
            rows = conn.execute(f"SELECT * FROM customers {clause} ORDER BY customer_id LIMIT ? OFFSET ?",
                                [*args, clamp_limit(limit), max(0, offset or 0)]).fetchall()
        return total, [_customer(r) for r in rows]

    # -- tickets -------------------------------------------------------------------

    def get_ticket(self, ticket_id: str) -> SupportTicket | None:
        """Fetch one ticket by ID (case-insensitive), or ``None``."""
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tickets WHERE ticket_id = ? COLLATE NOCASE",
                               (ticket_id.strip(),)).fetchone()
        return _ticket(row) if row else None

    def tickets_for_customer(self, customer_id: str, status: str | None = None) -> list[SupportTicket]:
        """All tickets raised by a customer, newest first, optionally filtered by status."""
        sql = "SELECT * FROM tickets WHERE raised_by = ? COLLATE NOCASE"
        args: list = [customer_id.strip()]
        if status:
            sql += " AND status = ?"
            args.append(status)
        with self.connect() as conn:
            rows = conn.execute(sql + " ORDER BY created_at DESC", args).fetchall()
        return [_ticket(r) for r in rows]

    def search_tickets(self, *, text=None, status=None, priority=None, raised_by=None, product_model=None,
                       resolved_by=None, created_from=None, created_to=None, limit=None,
                       offset=0) -> tuple[int, list[SupportTicket]]:
        """Filter tickets; text filters are partial and case-insensitive.

        ``text``: every word (stopwords ignored) must appear in the title or the description.
        ``product_model``: partial match, tolerating a leading brand ("Zentrix Z9 Plus" finds "Z9 Plus").
        """
        where, args = [], []
        for word in search_words(text) if text else []:
            where.append("(title LIKE ? ESCAPE '\\' COLLATE NOCASE OR description LIKE ? ESCAPE '\\' COLLATE NOCASE)")
            args += [like_pattern(word)] * 2
        if product_model:
            with self.connect() as conn:
                known = [r[0] for r in conn.execute("SELECT DISTINCT product_model FROM tickets "
                                                    "WHERE product_model IS NOT NULL")]
            variants = model_variants(product_model, known)
            where.append("(" + " OR ".join(["product_model LIKE ? ESCAPE '\\' COLLATE NOCASE"] * len(variants)) + ")")
            args += [like_pattern(v) for v in variants]
        if resolved_by:
            where.append("resolved_by LIKE ? ESCAPE '\\' COLLATE NOCASE")
            args.append(like_pattern(resolved_by))
        if raised_by:
            where.append("raised_by = ? COLLATE NOCASE")
            args.append(raised_by.strip())
        if status:
            where.append("status = ?")
            args.append(status)
        if priority:
            where.append("priority = ?")
            args.append(priority)
        if created_from:
            where.append("created_at >= ?")
            args.append(created_from)
        if created_to:
            where.append("created_at <= ?")
            args.append(created_to if "T" in created_to else f"{created_to}T23:59:59Z")
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM tickets {clause}", args).fetchone()[0]
            rows = conn.execute(f"SELECT * FROM tickets {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                                [*args, clamp_limit(limit), max(0, offset or 0)]).fetchall()
        return total, [_ticket(r) for r in rows]

    def next_ticket_id(self, conn: sqlite3.Connection) -> str:
        """Next sequential ticket ID (``TKT-000123``)."""
        last = conn.execute("SELECT MAX(CAST(SUBSTR(ticket_id, 5) AS INTEGER)) FROM tickets").fetchone()[0]
        return f"TKT-{(last or 0) + 1:06d}"

    def insert_ticket(self, *, title: str, description: str, raised_by: str, priority: str,
                      product_model: str | None) -> SupportTicket:
        """Insert a new open ticket and return it."""
        now = utc_now()
        with self.connect() as conn:
            ticket_id = self.next_ticket_id(conn)
            conn.execute(
                "INSERT INTO tickets (ticket_id, title, description, raised_by, product_model, status, priority, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?)",
                (ticket_id, title.strip(), description.strip(), raised_by, product_model, priority, now, now),
            )
        return self.get_ticket(ticket_id)

    def mark_resolved(self, ticket_id: str, resolved_by: str, remarks: str) -> SupportTicket:
        """Set a ticket to ``resolved`` with resolver, remarks and the current resolution date."""
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                "UPDATE tickets SET status = 'resolved', resolved_by = ?, resolution_remarks = ?, "
                "resolution_date = ?, updated_at = ? WHERE ticket_id = ?",
                (resolved_by.strip(), remarks.strip(), now, now, ticket_id),
            )
        return self.get_ticket(ticket_id)

    def ticket_stats(self) -> dict:
        """Counts by status and priority, the oldest open tickets and the models with most open issues."""
        with self.connect() as conn:
            by_status = dict(conn.execute("SELECT status, COUNT(*) FROM tickets GROUP BY status").fetchall())
            by_priority = dict(conn.execute("SELECT priority, COUNT(*) FROM tickets GROUP BY priority").fetchall())
            oldest = conn.execute(
                "SELECT ticket_id, title, priority, created_at FROM tickets WHERE status IN ('open', 'in_progress') "
                "ORDER BY created_at LIMIT 5").fetchall()
            models = conn.execute(
                "SELECT product_model, COUNT(*) AS n FROM tickets WHERE status IN ('open', 'in_progress') "
                "AND product_model IS NOT NULL GROUP BY product_model ORDER BY n DESC, product_model LIMIT 5").fetchall()
        return {
            "by_status": by_status,
            "by_priority": by_priority,
            "oldest_open": [dict(r) for r in oldest],
            "top_open_models": [{"product_model": m, "open_tickets": n} for m, n in models],
        }

    # -- seeding -------------------------------------------------------------------

    def load_seed(self, customers: list[dict], tickets: list[dict]) -> None:
        """Insert seed rows (used only when the database is empty)."""
        with self.connect() as conn:
            conn.executemany(
                "INSERT INTO customers VALUES (:customer_id, :full_name, :communication_address, :email, "
                ":phone_number, :credit_limit, :active_status, :remarks, :created_at, :updated_at)",
                [{**c, "active_status": int(c["active_status"])} for c in customers])
            conn.executemany(
                "INSERT INTO tickets VALUES (:ticket_id, :title, :description, :raised_by, :product_model, :status, "
                ":priority, :resolved_by, :resolution_date, :resolution_remarks, :created_at, :updated_at)", tickets)

    def reset(self) -> None:
        """Delete all tickets and customers (used by ``--reset-seed``)."""
        with self.connect() as conn:
            conn.execute("DELETE FROM tickets")
            conn.execute("DELETE FROM customers")
