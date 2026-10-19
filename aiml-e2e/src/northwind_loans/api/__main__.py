"""Start the API with uvicorn using API_HOST / API_PORT from config (.env).

    python -m northwind_loans.api

A SINGLE worker on purpose: the CPU is limited, and prometheus_client keeps its
counters in-process - several workers would each expose their own numbers.
"""

import uvicorn

from northwind_loans.api.observability import uvicorn_log_config
from northwind_loans.config import API_HOST, API_PORT


def main() -> None:
    """Run the server (Ctrl+C to stop)."""
    shown_host = "127.0.0.1" if API_HOST == "0.0.0.0" else API_HOST
    print(f"Swagger UI: http://{shown_host}:{API_PORT}/docs | metrics: /metrics", flush=True)
    uvicorn.run(
        "northwind_loans.api.main:app",
        host=API_HOST,
        port=API_PORT,
        workers=1,
        access_log=False,  # our middleware writes a richer JSON line per request
        log_config=uvicorn_log_config(),
    )


if __name__ == "__main__":
    main()
