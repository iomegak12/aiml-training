# Step 10 — Automated Tests + Container Packaging (plan & outcome)

## Context
Two parts:
- **(a)** Make sure the test files hold every case Ram named.
- **(b)** Package the API as a multi-stage Docker image, plus a compose stack with Prometheus and Grafana.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Docker engine | Ram started Docker Desktop. The tests and files were done first, then `docker info` was checked. |
| Build | `python:3.12-slim`, multi-stage, **uv in the builder** (`ghcr.io/astral-sh/uv:0.9.16`) |
| Volumes | API: bind `./logs:/app/logs`. Prometheus/Grafana: named volumes `prometheus-data` and `grafana-data`. Config mounted read-only. |
| Compose | No obsolete `version:` key; pinned `prom/prometheus:v3.5.0` and `grafana/grafana:12.1.0` |
| Models | Only the latest version is baked in (build arg `MODEL_VERSION`); no models volume |
| 5× income test | Kept in `test_business_rules.py` only (already covered) |
| Sample-rows test | Real `data/sample` CSV, scored by the synthetic conftest model |

## (a) Tests added (only the missing cases)

| File | Test |
|---|---|
| `test_cleaning.py` | `parse_dates` for `2024-01-05`, `05/01/2024` (5 Jan, no day-first guessing) and `05-Jan-2024`; failures counted |
| `test_predict.py` | all 10 sample rows: offer is None or within [0, 5× income] and divisible by 1000 |
| `test_predict.py` | credit score 580 → `credit_score_below_600`, still offered |
| `test_api.py` | batch of 3 (order kept) |
| `test_api.py` | `/metrics` contains `loan_api_requests_total{/predict,200}`, `loan_model_predictions_total`, `loan_model_offer_amount_inr_count`, `loan_model_info{model_version="1"}` |

These were already covered: parse_money, dedup keep-last, paise ÷100, missing income → None, /health, /ready, /predict 200/422, score 950.

**Result: 113 passed in 3.5 s** (about 8 s wall time including start-up), well under 30 s. The slowest test is a 0.42 s fixture setup.

## (b) Packaging files
- **`Dockerfile`**:
  - builder: `uv venv /opt/venv` → `uv pip install .` (runtime dependencies only)
  - runtime: copies the venv and `models/loan_offer_model_v${MODEL_VERSION}.{pkl,json}`
  - `ENV PROJECT_ROOT=/app API_HOST=0.0.0.0 API_PORT=8000`; non-root user `app`; `EXPOSE 8000`; no HEALTHCHECK
- **`.dockerignore`**: an allowlist (`*`, then `!pyproject.toml !README.md !src/ !models/`), so `.env`, data, tests and logs never enter the build context.
- **`docker-compose.yml`**:
  - `api`: `env_file: .env`, port `${API_PORT:-8000}`, bind mount `./logs`
  - `prometheus`: scrapes `api:8000/metrics` every 15 s
  - `grafana`: admin password from `GRAFANA_ADMIN_PASSWORD`, sign-up disabled
  - all three services `restart: unless-stopped`
- **Monitoring config**: `monitoring/prometheus/prometheus.yml` and `monitoring/grafana/provisioning/datasources/prometheus.yml`. Dashboards come in a later step.
- **Makefile**: `docker-build` (both tags, `MODEL_VERSION` = latest saved model), `up`, `down`, `logs`.
- **Fix**: uvicorn's `color_message` extra (ANSI codes) is now dropped from the JSON logs by the `DropColorMessage` filter, with a test.

## Outcome (2026-10-15)
- `docker images` shows `iomega/northwind-loans-api:0.1.0` and `:latest`, the same image ID (207 MB content).
- `docker run -d --name loan-api -p 8000:8000 --env-file .env -v ./logs:/app/logs …`:
  - `/health` 200, `/ready` 200 (model v4)
  - `/predict` 200 with offer 4,583,000
  - `loan_model_info{model_version="4"}`
  - the audit line written in the container appeared in the host's `logs/predictions.jsonl`
- `docker logs`: clean JSON. Startup shows model v4 loaded; request lines carry request_id, status, duration_ms and model_version; the 422 line is at WARNING.
- `docker inspect`:
  - user `app`, workdir `/app`, cmd `python -m northwind_loans.api`
  - bind mount `logs → /app/logs`, `PROJECT_ROOT=/app`
  - labels set, **Healthcheck: none**
  - the image holds only `loan_offer_model_v4.{pkl,json}`; no `.env`, data, tests or pytest
- `docker rm -f loan-api` removed the container; port 8000 is free.
- `docker compose config --quiet` validates. The full stack was **not** started: that isn't in the acceptance list, and it would pull the Prometheus and Grafana images.
