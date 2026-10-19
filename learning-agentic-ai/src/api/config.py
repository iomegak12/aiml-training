"""API server settings (.env with defaults) and fixed constants."""

import os
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

APP_NAME = "IT Support Agent API"
DISTRIBUTION_NAME = "learning-agentic-ai"

# Rate limiting (per client IP): RATE_LIMIT_REQUESTS per RATE_LIMIT_WINDOW_SECONDS;
# exceeding it blocks the IP for RATE_LIMIT_COOLDOWN_SECONDS, then its counter resets.
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_COOLDOWN_SECONDS = 30

LOG_FILE_NAME = "api.log"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 5

_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class ApiConfigurationError(ValueError):
    """Raised when an API setting in .env is invalid."""


def app_version() -> str:
    try:
        return version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return "0.0.0"


@dataclass(frozen=True)
class ApiSettings:
    host: str = "0.0.0.0"
    port: int = 8000
    log_dir: Path = Path("./logs")
    log_level: str = "INFO"
    root_path: str = ""  # path prefix when served behind a reverse proxy, e.g. "/api"
    forwarded_allow_ips: str = "127.0.0.1"  # proxies trusted for X-Forwarded-For / -Proto
    public_base_url: str | None = None  # public URL shown in the banner, e.g. "http://localhost/api"

    @property
    def log_file(self) -> Path:
        return self.log_dir / LOG_FILE_NAME

    @classmethod
    def from_env(cls) -> "ApiSettings":
        """Read API_HOST, API_PORT, LOG_DIR, LOG_LEVEL, API_ROOT_PATH, FORWARDED_ALLOW_IPS and
        PUBLIC_BASE_URL; unset values use the defaults."""
        load_dotenv(find_dotenv(usecwd=True))
        defaults = cls()

        host = os.getenv("API_HOST", "").strip() or defaults.host
        port_text = os.getenv("API_PORT", "").strip() or str(defaults.port)
        log_dir = Path(os.getenv("LOG_DIR", "").strip() or defaults.log_dir)
        log_level = (os.getenv("LOG_LEVEL", "").strip() or defaults.log_level).upper()
        root_path = os.getenv("API_ROOT_PATH", "").strip().rstrip("/")
        forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "").strip() or defaults.forwarded_allow_ips
        public_base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/") or None

        if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            raise ApiConfigurationError(f"API_PORT='{port_text}' must be a number between 1 and 65535")
        if log_level not in _LOG_LEVELS:
            raise ApiConfigurationError(f"LOG_LEVEL='{log_level}' must be one of: {', '.join(_LOG_LEVELS)}")

        if root_path and not root_path.startswith("/"):
            raise ApiConfigurationError(f"API_ROOT_PATH='{root_path}' must start with '/', e.g. /api")

        return cls(
            host=host,
            port=int(port_text),
            log_dir=log_dir,
            log_level=log_level,
            root_path=root_path,
            forwarded_allow_ips=forwarded_allow_ips,
            public_base_url=public_base_url,
        )
