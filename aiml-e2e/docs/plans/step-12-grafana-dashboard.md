# Step 13 — Grafana Dashboard + Prometheus Alerts

## Context
The compose stack (api + prometheus + grafana) is running, and the API exposes the 11 custom metrics from Step 9.
Step 13 adds:
- a provisioned Grafana dashboard: uid `loan-api`, 3 rows (Service health / Model behaviour / Data drift), 13 panels
- 5 Prometheus alert rules, group `loan-api`
- an acceptance run proving that every panel and alert query returns data

Live findings (read-only):
- Prometheus runs with `web.enable-lifecycle=false`, so `POST /-/reload` would be refused.
- Grafana accepts admin:admin and rejects admin:northwind. The password is fixed in the existing `grafana-data` DB.
- The API writes `manual_review="true"` / `"false"` (lowercase).
- Grafana is 12.1.0.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Alert acceptance | Query each alert's **signal** (the expression without its comparison) → it must return a value. Also run the full expression (empty means not firing) and show `/api/v1/alerts` with all 5 rules loaded. |
| Empty numerators | Add `or vector(0)` to the 4xx and 5xx numerators (panel 2 and HighServerErrorRate), like panel 8 |
| Grafana password | `docker compose exec grafana grafana cli admin reset-admin-password northwind`, and set `GRAFANA_ADMIN_PASSWORD=northwind` in `.env`; `.env.example` gets a placeholder. The volume is kept. |
| Scrape interval | 5 s (`evaluation_interval` 5 s), matching the dashboard's 5 s refresh; safe for `rate(...[1m])` after a 15 s wait |
| Grafana version | Keep 12.1.0, with classic dashboard JSON (schemaVersion 39, the Grafana 11 format) |
| Traffic | 55 valid + 5 invalid `/predict` |
| Validation | `promtool check config/rules` (inside the Prometheus image) + `tests/test_dashboard.py` (JSON only) |

Also: `manual_review="true"` is used everywhere, never `"True"`.

## Files
**`monitoring/grafana/dashboards/loan_api.json`**
- Top level: uid `loan-api`, title "Northwind Loan Offer API", `refresh: "5s"`, `time: now-15m → now`, `schemaVersion: 39`, tags, and a description with the disclaimer.
- Every target uses datasource `{"type": "prometheus", "uid": "prometheus"}`.
- Units: `reqps`, `percent`, `s`, `currencyINR`.

Row "Service health":

| # | Panel | Type and query |
|---|---|---|
| 1 | Requests/s by endpoint | timeseries; `sum by (endpoint) (rate(loan_api_requests_total[1m]))` |
| 2 | Error rate % | timeseries; 4xx and 5xx as two series, numerators with `or vector(0)` |
| 3 | /predict latency | timeseries; p50 and p95 `histogram_quantile` |
| 4 | In-flight requests | stat; `loan_api_requests_in_progress` |
| 5 | Validation errors by field | barchart; instant, table format, `xField: field` |

Row "Model behaviour":

| # | Panel | Type and query |
|---|---|---|
| 6 | Predictions/s by purpose | timeseries |
| 7 | Avg offer vs reference | timeseries; live `_sum/_count` rate, and reference `max(loan_model_reference_mean{feature="predicted_offer"})` drawn dashed via a field override |
| 8 | Manual review share % | timeseries; `manual_review="true"`, `or vector(0)` |
| 9 | Median offer/income | timeseries |

Row "Data drift":

| # | Panel | Type and query |
|---|---|---|
| 10 | Avg income vs reference | timeseries; reference dashed |
| 11 | Avg credit score vs reference | timeseries; reference dashed |
| 12 | Credit score distribution | bargauge; `sum by (le) (increase(…bucket[5m]))`, instant, **format heatmap**, legend `{{le}}` |
| 13 | Model version | stat; `loan_model_info`, legend `{{model_version}}`, `textMode: name` |

**`monitoring/grafana/provisioning/dashboards/dashboards.yml`**
- A file provider: folder "Northwind", path `/etc/grafana/dashboards`, `updateIntervalSeconds: 10`, `allowUiUpdates: false`.

**`monitoring/prometheus/alerts.yml`** (group `loan-api`). Every rule has `severity` plus `summary` and `description` annotations.

| Alert | Expression | For | Severity |
|---|---|---|---|
| LoanApiDown | `up{job="loan-api"} == 0` | 1m | critical |
| HighServerErrorRate | 5xx share with `or vector(0)`, `> 5` | 2m | critical |
| HighLatencyP95 | p95 `/predict` `> 0.5` | 2m | warning |
| IncomeDrift | as specified, with `scalar()` | 1m | warning |
| HighManualReviewShare | panel 8 expression `> 30` | 2m | warning |

**`monitoring/prometheus/prometheus.yml`**: `scrape_interval: 5s`, `evaluation_interval: 5s`, `rule_files: [alerts.yml]`.

**`docker-compose.yml`**:
- prometheus: mount the **directory** `./monitoring/prometheus:/etc/prometheus:ro` (single-file bind mounts go stale on Docker Desktop), and set `command: [--config.file=…, --storage.tsdb.path=/prometheus, --web.enable-lifecycle]`.
- grafana: add `./monitoring/grafana/dashboards:/etc/grafana/dashboards:ro`.

**`scripts/check_monitoring.py`** (uses `requests`; reads what is deployed, so nothing is duplicated):
- Panel queries come from the dashboard JSON (18 queries across the 13 panels).
- Alert expressions come from `GET :9090/api/v1/rules`.
- The signal is the expression with its trailing comparison removed by regex.
- Every query goes to `/api/v1/query`. The script prints a table (name | series | sample value | OK/EMPTY/ERROR) plus the alert states, and exits 1 if any panel query or signal is empty or fails.
- `make monitor` runs it and prints the URLs, replacing the placeholder.

**`tests/test_dashboard.py`**:
- uid, title, refresh, time range, schemaVersion
- 3 rows with the right titles, 13 panels
- every target datasource uid is `prometheus`
- no `manual_review="True"` anywhere
- panel 12 uses `format: heatmap`
- panel 7 has a dashed override on the reference query

**`.env`**: `GRAFANA_ADMIN_PASSWORD=northwind`. **`.env.example`**: `change-me`.

**Docs**: README (monitoring URLs and dashboard rows), CHANGELOG, TROUBLESHOOTING (reload refused without the lifecycle flag; the Grafana password applies only on first DB init; panels need 2 scrapes), `docs/plans/step-13-grafana-dashboards.md`.

## Verification (show real output)
1. `make test` (with the new dashboard test).
2. `promtool check config` and `check rules` via `docker run --rm --entrypoint promtool prom/prometheus:v3.5.0` on the mounted directory.
3. `docker compose up -d` recreates prometheus and grafana with the new mounts and flags. Then reset the Grafana password.
4. Run Ram's reload commands: `docker compose restart grafana` and `curl -X POST localhost:9090/-/reload` (expect 200).
5. `curl -s -u admin:northwind 'localhost:3000/api/search?query=Northwind'` finds the `loan-api` dashboard.
6. `curl -s localhost:9090/api/v1/rules | python -m json.tool | grep '"name"'` lists the group plus 5 alerts.
7. Send 60 `/predict`:
   - 55 valid: random complete rows from `data/processed` (`random_state=51`), so income and score sit near the training reference and IncomeDrift stays quiet
   - 5 invalid: score 950, Holiday, missing income, tenure 400, extra field
   - wait 15 s, then `python scripts/check_monitoring.py`
   - every panel query and alert signal must be non-empty, and all 5 alerts must be loaded
