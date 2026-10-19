# Step 13 — Grafana Dashboard + Prometheus Alerts (plan & outcome)

## Context
The compose stack (api + prometheus + grafana) was running, with 11 custom metrics from Step 9. This step adds:
- a provisioned Grafana dashboard: uid `loan-api`, 3 rows, 13 panels
- 5 Prometheus alerts
- proof that every panel and alert query returns data

Live findings before the change:
- Prometheus had `web.enable-lifecycle=false`, so reload would be refused.
- Grafana accepted admin:admin only (the password was set at first DB init).
- The API writes `manual_review="true"` (lowercase).
- Grafana is 12.1.0.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Alert acceptance | Query each alert's **signal** (the expression without its threshold), run the full expression too (empty = not firing), and show the rule state |
| Empty numerators | `or vector(0)` on the 4xx and 5xx numerators (panel 2, HighServerErrorRate), like panel 8 |
| Grafana password | `grafana cli admin reset-admin-password northwind`, and `.env` set to `northwind` (`.env.example`: `change-me`); volume kept |
| Scrape interval | 5 s scrape and evaluation (matches the 5 s refresh) |
| Grafana version | 12.1.0 kept; classic dashboard JSON, schemaVersion 39 |
| Traffic | 55 valid (random processed rows, `random_state=51`) + 5 invalid |
| Validation | `promtool check config/rules` + `tests/test_dashboard.py` |

## Files
- **`monitoring/grafana/dashboards/loan_api.json`**: 13 panels in 3 rows.
  - The panels use your expressions, with `manual_review="true"` and `or vector(0)` on the error rates.
  - The reference series (refId B) on panels 7, 10 and 11 are drawn dashed orange.
  - Panel 5 is a barchart (instant, table, `xField: field`).
  - Panel 12 is a bargauge (instant, `format: heatmap`).
  - Panel 13 is a stat (`textMode: name`, legend `{{model_version}}`).
- **`monitoring/grafana/provisioning/dashboards/dashboards.yml`**: file provider, folder "Northwind", path `/etc/grafana/dashboards`.
- **`monitoring/prometheus/alerts.yml`**: LoanApiDown, HighServerErrorRate, HighLatencyP95, IncomeDrift (with `scalar()`) and HighManualReviewShare, each with severity, summary and description.
- **`monitoring/prometheus/prometheus.yml`**: 5 s intervals, `rule_files: [alerts.yml]`.
- **`docker-compose.yml`**:
  - prometheus: `command` with `--web.enable-lifecycle`; mounts the whole `./monitoring/prometheus` directory read-only
  - grafana: mounts `./monitoring/grafana/dashboards`
- **`scripts/check_monitoring.py`** (`make monitor`): panel queries are read from the dashboard JSON and alert rules from `/api/v1/rules`. It prints a status table and exits 1 on any empty result or error.
- **`tests/test_dashboard.py`** (5 tests).
- **Fixes**:
  - `observability.init_label_series()` creates the known label combinations at 0. Without it the first 422s and manual reviews were invisible to `rate()`.
  - `pyproject.toml` gets `--basetemp=.pytest_tmp`, for the Windows `pytest-current` permission error.

## Outcome (2026-10-16)
- `make test`: **119 passed**. promtool: config valid, 5 rules found. Compose valid.
- `docker compose up -d` recreated the containers with the lifecycle flag on.
- `docker compose restart grafana` worked, and `curl -X POST localhost:9090/-/reload` returned **HTTP 200**.
- `curl -u admin:northwind 'localhost:3000/api/search?query=Northwind'` found folder "Northwind" and dashboard `loan-api` ("Northwind Loan Offer API").
- `/api/v1/rules`: group `loan-api` with LoanApiDown, HighServerErrorRate, HighLatencyP95, IncomeDrift and HighManualReviewShare.

### First run: exposed the label-initialisation bug
All queries were non-empty, but 4xx % and manual review % read 0. The fix was `init_label_series` plus an image rebuild.

### Second run: 60 /predict (55 × 200, 5 × 422), wait 15 s, `check_monitoring.py` (exit 0, 0 problems)

| Query | Value |
|---|---|
| 4xx % | 8.33 (5 / 60) |
| 5xx % | 0 |
| /predict p50 / p95 | 17.5 ms / 24.3 ms |
| Validation errors by field | credit_score, loan_purpose, annual_income, requested_tenure_months: 1 each |
| Average offer | live 16.3 L vs reference 19.9 L |
| Manual review share | 5.45% |
| Median offer / income | 1.23 |
| Average income | live 9.98 L vs reference 11.37 L |
| Average credit score | live 728.7 vs reference 730.6 |
| Credit score buckets | 9 |
| Model version | v4 |

Alert signals and states:

| Alert | Signal value | State |
|---|---|---|
| LoanApiDown | `up` = 1 | inactive |
| HighServerErrorRate | 0% | inactive |
| HighLatencyP95 | 0.024 s | inactive |
| IncomeDrift | 0.12 (below 0.25) | inactive |
| HighManualReviewShare | 5.5% | inactive |

## Not in this step
The traffic simulators (`simulate-normal/drift/bad`) and PSI drift computation.
