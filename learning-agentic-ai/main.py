"""Start the IT Support Agent API server.

Usage:
    uv run python main.py

Host, port, logging and proxy settings come from .env (API_HOST, API_PORT, LOG_DIR, LOG_LEVEL,
API_ROOT_PATH, FORWARDED_ALLOW_IPS, PUBLIC_BASE_URL).
"""

import uvicorn

from api.config import ApiSettings


def main() -> None:
    settings = ApiSettings.from_env()
    uvicorn.run(
        "api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=False,  # requests are logged by RequestContextMiddleware
        proxy_headers=True,  # client IP from X-Forwarded-For, only from trusted proxies
        forwarded_allow_ips=settings.forwarded_allow_ips,
    )


if __name__ == "__main__":
    main()
