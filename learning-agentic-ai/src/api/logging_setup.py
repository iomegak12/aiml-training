"""Logging: JSON lines to a rotating file, and a coloured one-line console format (rich)."""

import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.text import Text

from api.config import LOG_BACKUP_COUNT, LOG_FILE_NAME, LOG_MAX_BYTES

APP_LOGGER = "api"
ACCESS_LOGGER = "api.access"

_LEVEL_STYLES = {"DEBUG": "dim", "INFO": "green", "WARNING": "yellow", "ERROR": "bold red", "CRITICAL": "bold white on red"}


_BASE_KEYS = frozenset({"timestamp", "level", "logger", "message", "exception"})


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Structured fields come from `extra={"fields": {...}}`."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            # structured fields never override the base keys above
            **{k: v for k, v in getattr(record, "fields", {}).items() if k not in _BASE_KEYS},
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _status_style(status: int | None) -> str:
    if status is None or status >= 500:
        return "bold red"
    if status >= 400:
        return "yellow"
    if status >= 300:
        return "cyan"
    return "green"


class ConsoleHandler(logging.Handler):
    """Minimal, coloured console output: one line per request or message."""

    def __init__(self, console: Console | None = None) -> None:
        super().__init__()
        self.console = console or Console(stderr=True, soft_wrap=True)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            time = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            fields = getattr(record, "fields", {})
            line = Text(f"{time} ", style="dim")
            if "method" in fields:
                status = fields.get("status")
                line.append(f"{fields['method']:<6} ", style="bold magenta")
                line.append(f"{fields['path']} ", style="bold")
                line.append(f"{status} ", style=_status_style(status))
                line.append(f"{fields.get('duration_ms', 0):.0f}ms ", style="cyan")
                line.append(f"{fields.get('client_ip', '-')} ", style="dim")
                line.append(f"[{str(fields.get('request_id', ''))[:8]}]", style="dim")
            else:
                line.append(f"{record.levelname:<8} ", style=_LEVEL_STYLES.get(record.levelname, ""))
                line.append(record.getMessage())
            self.console.print(line, highlight=False)
            if record.exc_info:
                self.console.print(Text(logging.Formatter().formatException(record.exc_info), style="red"))
        except Exception:  # never let logging break a request
            self.handleError(record)


def setup_logging(log_dir: Path, level: str = "INFO", console: Console | None = None) -> Path:
    """Configure the `api` loggers (idempotent). Returns the log file path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / LOG_FILE_NAME

    logger = logging.getLogger(APP_LOGGER)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    file_handler = RotatingFileHandler(
        log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter())

    logger.addHandler(file_handler)
    logger.addHandler(ConsoleHandler(console))
    logger.setLevel(level)
    logger.propagate = False
    return log_file
