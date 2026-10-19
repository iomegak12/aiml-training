"""Colourful startup console for the MCP server (uses ``rich``, a FastMCP dependency)."""

from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mcp_servers.crm_support import __version__
from mcp_servers.crm_support.config import ServerSettings


def print_banner(settings: ServerSettings, counts: dict[str, int], seed_status: str, tools: list[str],
                 resources: list[str], prompts: list[str]) -> None:
    """Print the server's connection details, data status and capabilities."""
    console = Console()
    if console.width < 120:  # Docker logs and pipes report 80 columns; keep URIs and names unclipped
        console = Console(width=120, force_terminal=console.is_terminal or None)
    info = Table.grid(padding=(0, 2))
    info.add_column(style="bold cyan", justify="right")
    info.add_column()
    info.add_row("Endpoint", Text(settings.public_url, style="bold green underline"))
    info.add_row("Transport", "streamable HTTP")
    info.add_row("Listening on", f"{settings.host}:{settings.port}{settings.path}")
    info.add_row("Database", f"{settings.db_path}  [dim](SQLite)[/dim]")
    info.add_row("Records", f"[bold]{counts['customers']}[/bold] customers, [bold]{counts['tickets']}[/bold] tickets")
    info.add_row("Seed", seed_status)
    info.add_row("Auth", Text("DISABLED - demo server, publish on localhost only", style="bold yellow"))
    info.add_row("Health", f"http://localhost:{settings.port}/health")

    caps = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
    caps.add_column(f"Tools ({len(tools)})", style="green")
    caps.add_column(f"Resources ({len(resources)})", style="blue")
    caps.add_column(f"Prompts ({len(prompts)})", style="yellow")
    for i in range(max(len(tools), len(resources), len(prompts))):
        caps.add_row(*(items[i] if i < len(items) else "" for items in (tools, resources, prompts)))

    console.print(Panel(Group(info, Text(""), caps),
                        title=f"[bold white on blue] CRM & Support MCP Server v{__version__} [/]",
                        subtitle="[dim]FastMCP | Ctrl+C to stop[/dim]", border_style="bright_blue", expand=False))
