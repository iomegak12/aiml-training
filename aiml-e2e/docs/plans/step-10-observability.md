# Step 9 — Observability (JSON logs, request IDs, Prometheus metrics, prediction audit log)

## Context
Step 8's API works but is a black box. Step 9 adds:
- structured JSON logs, with one rich line per request
- an `X-Request-ID` header on every request
- Prometheus metrics at `GET /metrics`, covering:
  - traffic and latency
  - validation errors
  - offer and input distributions, for drift
  - reference means and model info
- a PII-safe prediction audit log

Everything runs in a single uvicorn worker (limited CPU; prometheus_client's in-process registry).

Read-only check: `pythonjsonlogger.json.JsonFormatter` works. The old `pythonjsonlogger.jsonlogger` path raises a DeprecationWarning, which our strict tests would fail on.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Access log | uvicorn `access_log=False`; our middleware line **is** the access log. Uvicorn's startup/error logs also use the JSON formatter. |
| Audit file | `logs/predictions.jsonl` (`PREDICTION_LOG` in config) |
| Self-traffic | Exclude `/metrics` only from request metrics and logs; `/health` and `/ready` are still counted |
| Batch audit | One line per applicant, sharing the request_id |

Choices of mine:
- The `endpoint` label is the route template, or `unmatched` for unknown paths, to keep cardinality low.
- The validation `field` label is the last string in `loc`, so list indexes drop out (`applicants[8].credit_score` → `credit_score`).
- Log level: INFO below 400, WARNING for 4xx, ERROR for 5xx.

## New: `src/northwind_loans/api/observability.py`

### Logging
- `json_formatter()`: `JsonFormatter("%(levelname)s %(name)s %(message)s", timestamp=True, rename_fields={"levelname": "level"})`.
- `uvicorn_log_config()`: a dictConfig with JSON stdout handlers for the `uvicorn`, `uvicorn.error` and `northwind_loans` loggers, at `LOG_LEVEL`.
- `log_request(...)`: one line per request, with message `"request"` and extra fields: `request_id`, `method`, `path`, `endpoint`, `status_code`, `duration_ms`, `model_version`.

### Metrics
All metrics are module-level on the default `REGISTRY`, so they are created once even if `create_app` runs many times in tests.

| Metric | Type | Labels / buckets |
|---|---|---|
| `loan_api_requests_total` | Counter | `method`, `endpoint`, `status_code` |
| `loan_api_request_duration_seconds` | Histogram | `endpoint`; buckets as specified |
| `loan_api_requests_in_progress` | Gauge | |
| `loan_api_validation_errors_total` | Counter | `field` |
| `loan_model_predictions_total` | Counter | `loan_purpose`, `manual_review` |
| `loan_model_offer_amount_inr` | Histogram | buckets as specified |
| `loan_model_offer_to_income_ratio` | Histogram | buckets as specified |
| `loan_model_input_annual_income_inr` | Histogram | buckets as specified |
| `loan_model_input_credit_score` | Histogram | buckets as specified |
| `loan_model_reference_mean` | Gauge | `feature` |
| `loan_model_info` | Gauge | `model_version`, `trained_at`, `sklearn_version` |

Helpers:
- `set_model_gauges(metadata)`: called once at startup. Sets the reference means for annual_income, credit_score and predicted_offer from `reference_profile.numeric`, and `model_info = 1` with `trained_at = created_at`.
- `record_predictions(records, results)`: one count per applicant. Offer and ratio go in the histograms only if there is an offer; the score only if present.
- `metrics_response()`: `generate_latest()` with `CONTENT_TYPE_LATEST`.

### Audit log
- `PII_FIELDS = {"age", "gender"}`.
- `log_predictions(path, request_id, endpoint, model_version, records, results)` appends JSON Lines under a `threading.Lock`.
- Each line holds: `timestamp` (UTC ISO), `request_id`, `endpoint`, `model_version`, `input` (minus PII), `output`.

## Changes to `api/main.py`
- `create_app(model_dir=MODEL_DIR, prediction_log=PREDICTION_LOG)`.
- `@app.middleware("http")`:
  1. Read `X-Request-ID` or generate `uuid4`, and put it in `request.state.request_id`.
  2. Skip `/metrics`.
  3. Increment the in-progress gauge and start a timer.
  4. Run `call_next`; on an exception, use status 500 and re-raise.
  5. Take the endpoint from `request.scope["route"].path`.
  6. Record the counter and histogram, then `log_request`.
  7. Set `X-Request-ID` on the response.
- `@app.exception_handler(RequestValidationError)`: count each error's field, then return FastAPI's own `request_validation_exception_handler` (the unchanged 422 body).
- `lifespan`: calls `set_model_gauges(predictor.metadata)` after loading.
- `/predict` and `/predict/batch` call `record_predictions` and `log_predictions`.
- `GET /metrics` returns `metrics_response()` (`include_in_schema=False`).

## Other changes
- `config.py`: `PREDICTION_LOG = LOG_DIR / "predictions.jsonl"`.
- `api/__main__.py`: `uvicorn.run(..., workers=1, access_log=False, log_config=uvicorn_log_config())`, with a comment on why there is a single worker.
- `tests/test_observability.py` (TestClient, tmp prediction log, `REGISTRY.get_sample_value` deltas):
  - the request-ID header is echoed, or a valid UUID4 is generated
  - `/metrics` has the right content type and all 11 `loan_` metric names, and is not self-counted
  - validation errors count `credit_score` and `loan_purpose`, while the 422 body is unchanged
  - prediction counters and histograms increase
  - the reference means and `model_info` gauge are set
  - the audit log gets 1 line per applicant (batch of 2 → 2), with no age or gender, and the request_id matches
  - the JSON formatter emits `timestamp`, `level` and the extra fields
- README (observability section), CHANGELOG, TROUBLESHOOTING, `docs/plans/step-09-observability.md`.

## Verification (show real output)
1. `make test`: all tests pass.
2. Start `make serve` in the background. Send 20 valid `/predict` requests (varied purpose, income and score, a few without a credit score) and 3 invalid ones (score 950, Holiday, missing income).
3. `curl /metrics | grep ^loan_`: print the lines.
4. `tail -2 logs/predictions.jsonl`, and confirm with Python that `age` and `gender` are absent.
5. Show one JSON request line from the server console.
6. Stop the server and confirm port 8000 is free.
