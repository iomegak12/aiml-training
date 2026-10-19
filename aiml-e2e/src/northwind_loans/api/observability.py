"""Observability for the API: JSON logs, Prometheus metrics, prediction audit log.

- Logs   : one JSON object per line (python-json-logger), incl. one line per request.
- Metrics: prometheus_client objects on the default registry, served at GET /metrics.
           Run a SINGLE uvicorn worker - each process would otherwise keep its own counters.
- Audit  : logs/predictions.jsonl, one line per applicant, PII (age, gender) removed.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pythonjsonlogger.json import JsonFormatter

from northwind_loans.config import LOG_LEVEL

request_logger = logging.getLogger("northwind_loans.api.requests")

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------
LOG_FORMAT = "%(levelname)s %(name)s %(message)s"
RENAME_FIELDS = {"levelname": "level"}


class DropColorMessage(logging.Filter):
    """Remove uvicorn's `color_message` extra (ANSI codes) from JSON log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.__dict__.pop("color_message", None)
        return True


def json_formatter() -> JsonFormatter:
    """JSON formatter: timestamp, level, logger name, message + any `extra` fields."""
    return JsonFormatter(LOG_FORMAT, timestamp=True, rename_fields=RENAME_FIELDS)


def uvicorn_log_config() -> dict:
    """logging.dictConfig for uvicorn + our package: everything as JSON on stdout.

    uvicorn's own access log is disabled (access_log=False); our middleware's
    request line replaces it because it also has request_id and duration.
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.json.JsonFormatter",
                "fmt": LOG_FORMAT,
                "timestamp": True,
                "rename_fields": RENAME_FIELDS,
            }
        },
        "filters": {"drop_color": {"()": DropColorMessage}},
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": ["drop_color"],
                "stream": "ext://sys.stdout",
            }
        },
        "loggers": {
            "uvicorn": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": False},
            "uvicorn.access": {"handlers": [], "level": "WARNING", "propagate": False},
            "northwind_loans": {"handlers": ["stdout"], "level": LOG_LEVEL, "propagate": False},
        },
    }


def log_request(request_id: str, method: str, path: str, endpoint: str,
                status_code: int, duration_ms: float, model_version: int | None) -> None:
    """One structured log line per request (INFO, WARNING for 4xx, ERROR for 5xx)."""
    level = logging.ERROR if status_code >= 500 else logging.WARNING if status_code >= 400 \
        else logging.INFO
    request_logger.log(level, "request", extra={
        "request_id": request_id,
        "method": method,
        "path": path,
        "endpoint": endpoint,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "model_version": model_version,
    })


# --------------------------------------------------------------------------
# Prometheus metrics (module level: created once per process)
# --------------------------------------------------------------------------
REQUESTS_TOTAL = Counter(
    "loan_api_requests_total", "HTTP requests", ["method", "endpoint", "status_code"]
)
REQUEST_DURATION = Histogram(
    "loan_api_request_duration_seconds", "Request duration in seconds", ["endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5],
)
REQUESTS_IN_PROGRESS = Gauge("loan_api_requests_in_progress", "Requests being processed")
VALIDATION_ERRORS = Counter(
    "loan_api_validation_errors_total", "Request validation errors (422)", ["field"]
)
PREDICTIONS_TOTAL = Counter(
    "loan_model_predictions_total", "Applicants scored", ["loan_purpose", "manual_review"]
)
OFFER_AMOUNT = Histogram(
    "loan_model_offer_amount_inr", "Offered amount (INR)",
    buckets=[100_000, 250_000, 500_000, 1_000_000, 2_500_000, 5_000_000,
             10_000_000, 25_000_000, 50_000_000],
)
OFFER_TO_INCOME = Histogram(
    "loan_model_offer_to_income_ratio", "Offered amount / annual income",
    buckets=[0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5],
)
INPUT_INCOME = Histogram(
    "loan_model_input_annual_income_inr", "Annual income of applicants (INR)",
    buckets=[200_000, 400_000, 600_000, 800_000, 1_000_000, 1_500_000,
             2_000_000, 3_000_000, 5_000_000, 10_000_000],
)
INPUT_CREDIT_SCORE = Histogram(
    "loan_model_input_credit_score", "Credit score of applicants (when present)",
    buckets=[550, 600, 650, 700, 750, 800, 850, 900],
)
REFERENCE_MEAN = Gauge(
    "loan_model_reference_mean", "Training-set mean from the model metadata", ["feature"]
)
MODEL_INFO = Gauge(
    "loan_model_info", "Loaded model (value is always 1)",
    ["model_version", "trained_at", "sklearn_version"],
)

REFERENCE_FEATURES: list[str] = ["annual_income", "credit_score", "predicted_offer"]

# Label values created at 0 on start-up (see init_label_series)
TRACKED_ROUTES: list[tuple[str, str]] = [
    ("POST", "/predict"), ("POST", "/predict/batch"),
    ("GET", "/health"), ("GET", "/ready"), ("GET", "/model-info"),
]
TRACKED_STATUS_CODES: list[str] = ["200", "422", "500", "503"]


def init_label_series(loan_purposes: list[str], fields: list[str]) -> None:
    """Create the known label combinations at 0.

    A labelled counter only appears in /metrics after its first increment, so
    Prometheus would see e.g. the first 422s as a series that *starts* at 5 and
    rate() would report 0. Starting every known series at 0 avoids that.
    """
    for method, endpoint in TRACKED_ROUTES:
        for status_code in TRACKED_STATUS_CODES:
            REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=status_code)
    for purpose in loan_purposes:
        for review in ("true", "false"):
            PREDICTIONS_TOTAL.labels(loan_purpose=purpose, manual_review=review)
    for field in fields:
        VALIDATION_ERRORS.labels(field=field)


def set_model_gauges(metadata: dict) -> None:
    """Set the reference means and model info once at start-up."""
    numeric = metadata.get("reference_profile", {}).get("numeric", {})
    for feature in REFERENCE_FEATURES:
        if feature in numeric:
            REFERENCE_MEAN.labels(feature=feature).set(numeric[feature]["mean"])
    MODEL_INFO.labels(
        model_version=str(metadata["version"]),
        trained_at=metadata["created_at"],
        sklearn_version=metadata["sklearn_version"],
    ).set(1)


def record_request(method: str, endpoint: str, status_code: int, duration_s: float) -> None:
    """Count and time one HTTP request."""
    REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    REQUEST_DURATION.labels(endpoint=endpoint).observe(duration_s)


def record_validation_errors(errors: list[dict]) -> None:
    """Count each validation error by field name (list indexes are ignored)."""
    for error in errors:
        names = [str(part) for part in error.get("loc", []) if isinstance(part, str)]
        VALIDATION_ERRORS.labels(field=names[-1] if names else "unknown").inc()


def record_predictions(records: list[dict], results: list[dict]) -> None:
    """Update the model metrics for each scored applicant."""
    for record, result in zip(records, results):
        PREDICTIONS_TOTAL.labels(
            loan_purpose=str(record.get("loan_purpose")),
            manual_review=str(result["manual_review"]).lower(),
        ).inc()
        income = record.get("annual_income")
        if income:
            INPUT_INCOME.observe(income)
        if record.get("credit_score") is not None:
            INPUT_CREDIT_SCORE.observe(record["credit_score"])
        offer = result.get("offered_amount")
        if offer is not None:
            OFFER_AMOUNT.observe(offer)
            if income:
                OFFER_TO_INCOME.observe(offer / income)


def metrics_response() -> Response:
    """Prometheus exposition of all metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# --------------------------------------------------------------------------
# Prediction audit log (JSON Lines)
# --------------------------------------------------------------------------
PII_FIELDS: set[str] = {"age", "gender"}
_audit_lock = threading.Lock()


def log_predictions(path: Path, request_id: str, endpoint: str, model_version: int,
                    records: list[dict], results: list[dict]) -> None:
    """Append one JSON line per applicant (input without PII + output)."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    lines = []
    for record, result in zip(records, results):
        lines.append(json.dumps({
            "timestamp": timestamp,
            "request_id": request_id,
            "endpoint": endpoint,
            "model_version": model_version,
            "input": {key: value for key, value in record.items() if key not in PII_FIELDS},
            "output": result,
        }))
    path.parent.mkdir(parents=True, exist_ok=True)
    with _audit_lock, path.open("a", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")
