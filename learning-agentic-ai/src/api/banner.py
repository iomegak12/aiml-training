"""Colourful startup banner (rich)."""

import os
import platform

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from api.config import (
    APP_NAME,
    RATE_LIMIT_COOLDOWN_SECONDS,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    ApiSettings,
    app_version,
)
from api.runtime import RuntimeInfo


def print_banner(settings: ApiSettings, info: RuntimeInfo, console: Console | None = None) -> None:
    console = console or Console()
    host = "localhost" if settings.host in ("0.0.0.0", "::") else settings.host
    base_url = settings.public_base_url or f"http://{host}:{settings.port}{settings.root_path}"

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", justify="right")
    table.add_column()

    def section(title: str) -> None:
        table.add_row("", "")
        table.add_row(Text(title, style="bold magenta"), "")

    section("Server")
    table.add_row("Listening", f"{settings.host}:{settings.port}")
    table.add_row("Base URL", Text(base_url, style="underline bright_blue"))
    table.add_row("Swagger UI", Text(f"{base_url}/docs", style="underline bright_blue"))
    table.add_row("ReDoc", Text(f"{base_url}/redoc", style="underline bright_blue"))
    table.add_row("OpenAPI", Text(f"{base_url}/openapi.json", style="underline bright_blue"))
    table.add_row("Health / Ready", f"{base_url}/health  ·  {base_url}/ready")

    section("Agent")
    table.add_row("Model", info.model or Text("not configured", style="bold red"))
    table.add_row("Reasoning effort", info.reasoning_effort or "-")
    table.add_row(
        "OpenAI API key",
        Text("set", style="bold green") if info.api_key_set else Text("MISSING (add OPENAI_API_KEY to .env)", style="bold red"),
    )
    table.add_row("Ticket database", info.database_path or Text("not configured", style="bold red"))

    section("Operations")
    table.add_row("Endpoints", "POST /chat · POST /chat-streaming · POST /chat/decision")
    table.add_row(
        "Rate limit",
        f"{RATE_LIMIT_REQUESTS} req / {RATE_LIMIT_WINDOW_SECONDS}s per IP, then {RATE_LIMIT_COOLDOWN_SECONDS}s block",
    )
    table.add_row("Log file", f"{settings.log_file.resolve()} (JSON, {settings.log_level})")
    table.add_row("Runtime", f"Python {platform.python_version()} · PID {os.getpid()}")

    if info.error:
        table.add_row("", "")
        table.add_row(Text("Not ready", style="bold yellow"), Text(info.error, style="yellow"))

    title = Text(f" {APP_NAME}  v{app_version()} ", style="bold white")
    status = Text(" READY ", style="bold black on green") if not info.error else Text(" DEGRADED ", style="bold black on yellow")
    console.print(Panel(table, title=title, subtitle=status, border_style="bright_blue", expand=False, padding=(0, 2)))
