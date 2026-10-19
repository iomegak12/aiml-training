# Step 9 — Observability (plan & outcome)

## Context
Step 8's API worked but was a black box. Step 9 adds:
- structured JSON logs, with one rich line per request
- an `X-Request-ID` header on every request
- Prometheus metrics at `GET /metrics`
- a PII-safe prediction audit log

Everything runs in a single uvicorn worker (limited CPU; prometheus_client keeps metrics per process).

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Access log | uvicorn `access_log=False`; our middleware line **is** the access log. Uvicorn's startup/error logs are JSON too. |
| Audit file | `logs/predictions.jsonl` (`PREDICTION_LOG` in config) |
| Self-traffic | Only `/metrics` is excluded from request metrics and logs |
| Batch audit | One line per applicant, sharing the request_id |
| Endpoint label | Route template, or `unmatched` (low cardinality) |
| Validation `field` | Last string in `loc` (list indexes ignored) |
| Log level | INFO below 400, WARNING for 4xx, ERROR for 5xx |

## Files
- **`api/observability.py`**:
  - logging: `json_formatter()` (`pythonjsonlogger.json`; the old `.jsonlogger` path is deprecated), `uvicorn_log_config()`, `log_request()`
  - the 11 metrics, created once at module level
  - metric helpers: `set_model_gauges`, `record_request`, `record_validation_errors`, `record_predictions`, `metrics_response`
  - audit log: `log_predictions()` (`PII_FIELDS = {"age", "gender"}`, thread lock)
- **`api/main.py`**:
  - `create_app(model_dir, prediction_log)`
  - the `observe_requests` middleware
  - a `RequestValidationError` handler that counts fields and then returns FastAPI's own 422 body
  - `set_model_gauges` in lifespan
  - a shared `score()` helper used by `/predict` and `/predict/batch`
  - `GET /metrics` (hidden from the OpenAPI schema)
- **`api/__main__.py`**: `uvicorn.run(workers=1, access_log=False, log_config=uvicorn_log_config())`.
- **`config.py`**: `PREDICTION_LOG`.
- **Tests**:
  - `tests/test_observability.py` (9): request ID echoed or generated as UUID4; all metric names and the content type; `/metrics` not self-counted; counter and histogram deltas; validation-field counts with the 422 body unchanged; model metrics; reference and info gauges; audit log (one line per applicant, no PII); JSON log-line fields.
  - `test_api.py` now writes its audit log to a tmp path.
  - Full suite: 104 passed.

## Outcome (2026-10-15, live server, model v4)
- 20 valid `/predict` → all 200. 3 invalid → all 422 (score 950, Holiday, missing income).
- `/metrics` (`text/plain; version=0.0.4`):

| Metric | Value seen |
|---|---|
| `loan_api_requests_total{/predict,200}` | 20 |
| `loan_api_requests_total{/predict,422}` | 3 |
| `loan_api_validation_errors_total` | `credit_score`, `loan_purpose`, `annual_income`: 1 each |
| `loan_model_predictions_total` | 20 across 5 purposes; 7 with `manual_review="true"` |
| `loan_model_input_credit_score_count` | 17 (3 requests had no score) |
| `loan_model_reference_mean` | annual_income 1,137,435; credit_score 730.6; predicted_offer 1,986,944 |
| `loan_model_info` | `{model_version="4", sklearn_version="1.5.2", trained_at="2026-10-15T10:39:02+00:00"} 1` |
| `/predict` latency | 17 of 23 requests ≤ 25 ms, all ≤ 50 ms |

- Audit log: 20 lines; `age`/`gender` in input: 0. Each line holds timestamp, request_id, endpoint, model_version, input and output.
- Console line:
  `{"level": "INFO", "name": "northwind_loans.api.requests", "message": "request", "request_id": "req-005", "method": "POST", "path": "/predict", "endpoint": "/predict", "status_code": 200, "duration_ms": 22.8, "model_version": 4, "timestamp": "..."}`
- The server was stopped (PID 2284) and port 8000 was free afterwards.

## Not in this step
Docker, Prometheus/Grafana containers and dashboards, the traffic simulators, and drift/PSI.
