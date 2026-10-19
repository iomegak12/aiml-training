# Step 10 — Automated Tests + Container Packaging

## Context
Steps 1–9 built the pipeline, API and observability, and 104 tests already pass in about 2.5 s.
Step 10 has two parts:
- **(a)** Make sure the test files Ram listed hold every case he named.
- **(b)** Package the API as a multi-stage Docker image (`iomega/northwind-loans-api:0.1.0` + `:latest`), with a compose file that adds Prometheus and Grafana.

Read-only findings:
- Docker client 29.8.1 and Compose v5.5.1 are installed. The Docker Desktop engine is **not running**; Ram will start it before the build.
- `models/` holds v1–v4; v4 is the latest.
- Existing tests already cover parse_money, dedup keep-last, paise ÷100, the 5× cap (test_business_rules), missing income → None, /health, /ready, /predict 200/422 and score 950.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Docker engine | Ram starts Docker Desktop. I write the files and run the tests first, then check `docker info` before building. |
| Build | `python:3.12-slim`, multi-stage; **uv in the builder** (`COPY --from=ghcr.io/astral-sh/uv:0.9.16 /uv /bin/uv`, the same uv as local) |
| Volumes | API: bind `./logs:/app/logs`. Prometheus and Grafana: named volumes `prometheus-data` and `grafana-data`. Config mounted read-only. |
| Compose | **No obsolete `version:` key.** Image tags pinned: `prom/prometheus:v3.5.0`, `grafana/grafana:12.1.0` |
| Models | Only the latest version is baked in (build arg `MODEL_VERSION`, today 4); no models volume |
| 5× income test | Stays in `test_business_rules.py` only (already covered) |
| Sample-rows test | Real `data/sample` CSV, scored by the synthetic conftest model (works in CI and fresh clones) |

## (a) Tests: only the missing cases are added
- `tests/test_cleaning.py`: a parametrized `parse_dates` test with one case per format: `2024-01-05` (YYYY-MM-DD), `05/01/2024` (DD/MM/YYYY, must give 5 Jan, no day-first guessing) and `05-Jan-2024` (DD-Mon-YYYY).
- `tests/test_predict.py`:
  - `test_all_sample_rows_respect_business_rules`: `read_raw_csv(SAMPLE_DATA)` → `predict_frame`. Every offer is None, or `0 ≤ offer ≤ 5 × income` and `% 1000 == 0` (income from `standardize_frame`). Also checks there are 10 rows.
  - `test_credit_score_580_triggers_manual_review`.
- `tests/test_api.py`:
  - `test_batch_of_3`: 3 results in order
  - `test_metrics_contains_key_values`: after a predict, `/metrics` has `loan_api_requests_total{…"/predict"…,"200"}`, `loan_model_predictions_total`, `loan_model_offer_amount_inr_count` and `loan_model_info{model_version="1"…} 1.0`
- Acceptance: `pytest -q --durations=5` shows the summary, and the total must be < 30 s.

## (b) Packaging

### `Dockerfile` (no HEALTHCHECK)
```
FROM python:3.12-slim AS builder
  COPY --from=ghcr.io/astral-sh/uv:0.9.16 /uv /bin/uv
  uv venv /opt/venv; COPY pyproject.toml README.md src/; uv pip install --no-cache .   (runtime deps only)
FROM python:3.12-slim AS runtime
  ARG MODEL_VERSION
  ENV PATH=/opt/venv/bin:$PATH PROJECT_ROOT=/app API_HOST=0.0.0.0 API_PORT=8000 PYTHONUNBUFFERED=1
  non-root user "app"; COPY --from=builder /opt/venv
  COPY models/loan_offer_model_v${MODEL_VERSION}.pkl/.json -> /app/models/
  mkdir /app/logs; USER app; EXPOSE 8000; CMD ["python", "-m", "northwind_loans.api"]
```
- `PROJECT_ROOT=/app` is required: in a non-editable install, `config.py`'s `parents[2]` points into site-packages.
- `MODEL_SIGNING_KEY` is **not** baked in. It comes from `--env-file .env` or compose `env_file`. Without it, signature verification fails and `/ready` returns 503 (documented).

### `.dockerignore` (allowlist)
- `*` excludes everything, then re-include `pyproject.toml`, `README.md`, `src/` and `models/`.
- Exclude `**/__pycache__`.
- So `.env`, `data/`, `.venv/`, `tests/`, `logs/` and `reports/` never enter the build context.

### `docker-compose.yml` (no `version:`)
- `name: northwind-loans`.
- `api`:
  - `image: iomega/northwind-loans-api:0.1.0`, `env_file: .env`
  - `ports: "${API_PORT:-8000}:${API_PORT:-8000}"`, `volumes: ./logs:/app/logs`
- `prometheus`:
  - `prom/prometheus:v3.5.0`, port 9090
  - mounts `./monitoring/prometheus/prometheus.yml` read-only and `prometheus-data:/prometheus`
  - `depends_on: api`
- `grafana`:
  - `grafana/grafana:12.1.0`, port 3000
  - mounts `./monitoring/grafana/provisioning` read-only and `grafana-data:/var/lib/grafana`
  - `GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}`, `GF_USERS_ALLOW_SIGN_UP=false`
  - `depends_on: prometheus`
- `volumes: prometheus-data, grafana-data`.

### Monitoring config
- `monitoring/prometheus/prometheus.yml`: `scrape_interval: 15s`; job `loan-api` → `api:8000/metrics`; job `prometheus` → self.
- `monitoring/grafana/provisioning/datasources/prometheus.yml`: Prometheus datasource `http://prometheus:9090`, default, uid `prometheus`. Dashboards come in a later step; the folder keeps `.gitkeep`.
- `.env.example` + `.env`: `GRAFANA_ADMIN_PASSWORD`.

### Makefile
- `IMAGE := iomega/northwind-loans-api`, `VERSION := 0.1.0`.
- `MODEL_VERSION = $(shell $(PY) -c "...list_versions()[-1]")` is lazy, so it is only evaluated by docker-build.
- `docker-build`: `docker build --build-arg MODEL_VERSION=$(MODEL_VERSION) -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .`
- `up`: `docker compose up -d`. `down`: `docker compose down`. `logs`: `docker compose logs -f api`.
- `monitor` and `simulate-*` stay placeholders.

## Docs
README (Docker section + URLs), CHANGELOG, TROUBLESHOOTING (daemon not running; `/ready` 503 in a container means no `--env-file`; bind-mount permissions), `docs/plans/step-10-tests-and-packaging.md`.

## Verification (show real output)
1. `pytest -q --durations=5`: summary, total < 30 s.
2. `docker info` must answer (Ram started Docker Desktop).
3. `make docker-build`, then `docker images iomega/northwind-loans-api` shows 0.1.0 and latest.
4. Run the container:
   `docker run -d --name loan-api -p 8000:8000 --env-file .env -v ./logs:/app/logs iomega/northwind-loans-api:0.1.0`
   then curl `/health`, `/ready` (model v4) and `/predict`.
5. `docker logs loan-api`: JSON lines.
6. `docker inspect`: image, tags, env (key masked), mounts, ports, user, cmd; the image has no Healthcheck.
7. `docker rm -f loan-api`, then confirm port 8000 is free.
8. `docker compose config --quiet`: the compose file validates. Not `up`, which isn't in the acceptance list and would pull the Prometheus/Grafana images.
