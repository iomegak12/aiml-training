"""Server settings read from environment variables (``.env`` locally, ``env_file`` in Docker)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    """Interpret environment variable ``name`` as a boolean."""
    raw = os.getenv(name, "").strip().lower()
    return default if not raw else raw in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class ServerSettings:
    """Runtime configuration of the CRM/support MCP server.

    Attributes:
        db_path: SQLite database file (``CRM_DB_PATH``).
        host: Interface to bind (``MCP_HOST``); ``0.0.0.0`` inside the container.
        port: TCP port (``MCP_PORT``).
        path: HTTP path of the MCP endpoint (``MCP_PATH``).
        public_url: URL shown in the banner (``MCP_PUBLIC_URL``), i.e. how clients reach the server.
        seed_on_start: Seed demo data when the database is empty (``CRM_SEED_ON_START``).
        log_level: Uvicorn/FastMCP log level (``MCP_LOG_LEVEL``).
    """

    db_path: Path
    host: str
    port: int
    path: str
    public_url: str
    seed_on_start: bool
    log_level: str

    @classmethod
    def from_env(cls) -> ServerSettings:
        """Build settings from the environment, loading ``.env`` when python-dotenv is available."""
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:  # the slim Docker image does not ship python-dotenv
            pass
        port = int(os.getenv("MCP_PORT", "8765"))
        path = "/" + os.getenv("MCP_PATH", "/mcp").strip("/")
        return cls(
            db_path=Path(os.getenv("CRM_DB_PATH", "data/crm/crm_support.db")),
            host=os.getenv("MCP_HOST", "127.0.0.1"),
            port=port,
            path=path,
            public_url=os.getenv("MCP_PUBLIC_URL", f"http://localhost:{port}{path}"),
            seed_on_start=_env_bool("CRM_SEED_ON_START", True),
            log_level=os.getenv("MCP_LOG_LEVEL", "warning").lower(),
        )
