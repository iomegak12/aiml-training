"""Load the CRM & Support MCP tools and split them between the specialist agents.

``config/mcp_servers.json`` lists the MCP servers (``${VAR}`` placeholders are expanded from
the environment). Tools are discovered with LangChain's ``MCPAdapter`` and grouped:

- **customer** (Customer Support agent): ``get_customer_profile``, ``search_customer_profiles``
- **ticket_read** (Ticket Management agent): ``get_tickets_by_customer``, ``search_tickets``
- **ticket_write** (only the graph's ``execute_actions`` node, after human approval):
  ``register_ticket``, ``resolve_ticket``

If the server is unreachable the toolkit is returned with ``available=False`` and the
Coordinator plans without the CRM agents instead of failing.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.tools import BaseTool

from agentic_rag.config import AgentSettings

CUSTOMER_TOOLS = ("get_customer_profile", "search_customer_profiles")
TICKET_READ_TOOLS = ("get_tickets_by_customer", "search_tickets")
TICKET_WRITE_TOOLS = ("register_ticket", "resolve_ticket")


@dataclass
class CrmToolkit:
    """MCP tools of the CRM & Support server, grouped by the agent that may use them."""

    url: str
    available: bool
    customer: list[BaseTool] = field(default_factory=list)
    ticket_read: list[BaseTool] = field(default_factory=list)
    ticket_write: dict[str, BaseTool] = field(default_factory=dict)
    error: str | None = None

    def describe(self) -> str:
        """One-line status for logs and notebooks."""
        if not self.available:
            return f"CRM MCP server unavailable at {self.url}: {self.error}"
        return (f"CRM MCP server at {self.url}: customer={[t.name for t in self.customer]}, "
                f"ticket_read={[t.name for t in self.ticket_read]}, ticket_write={list(self.ticket_write)}")


def _expand(value: str) -> str:
    """Replace ``${VAR}`` placeholders with environment values."""
    return re.sub(r"\$\{([A-Z0-9_]+)\}", lambda m: os.getenv(m.group(1), ""), value)


def server_url(settings: AgentSettings, name: str = "crm_support") -> str:
    """URL of MCP server ``name`` from ``MCP_CONFIG_PATH`` (falls back to ``CRM_MCP_URL``)."""
    path: Path = settings.mcp_config_path
    if path.exists():
        config = json.loads(path.read_text(encoding="utf-8"))
        server = config.get("mcpServers", {}).get(name)
        if server and server.get("url"):
            return _expand(server["url"]) or settings.crm_mcp_url
    return settings.crm_mcp_url


async def load_crm_tools(settings: AgentSettings, timeout: float = 10) -> CrmToolkit:
    """Discover the CRM tools; never raises - an unreachable server yields ``available=False``."""
    url = server_url(settings)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # langchain.mcp is beta and says so on import
        from langchain.mcp import MCPAdapter
    try:
        tools = await asyncio.wait_for(MCPAdapter(url).list_tools(), timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - any connection problem means "unavailable"
        return CrmToolkit(url=url, available=False, error=f"{type(exc).__name__}: {exc}"[:300])
    by_name = {t.name: t for t in tools}
    missing = [n for n in (*CUSTOMER_TOOLS, *TICKET_READ_TOOLS, *TICKET_WRITE_TOOLS) if n not in by_name]
    return CrmToolkit(
        url=url,
        available=not missing,
        customer=[by_name[n] for n in CUSTOMER_TOOLS if n in by_name],
        ticket_read=[by_name[n] for n in TICKET_READ_TOOLS if n in by_name],
        ticket_write={n: by_name[n] for n in TICKET_WRITE_TOOLS if n in by_name},
        error=f"missing tools: {missing}" if missing else None,
    )


def tool_text(result: object) -> str:
    """Plain text of an MCP tool result (a list of content blocks, or a string)."""
    if isinstance(result, list):
        return "\n".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in result)
    return str(result)
