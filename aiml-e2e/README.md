# Northwind Finance — Maximum Loan Offer Prediction

An end-to-end ML application, built step by step in a live training session
(**Complete ML Application Development — E2E**).

> ⚠️ **Disclaimer:** This is an **educational demonstration built on synthetic data**.
> Northwind Finance is fictional. This project and its model must **never be used
> for real credit decisions**.

## Project goal

Predict the **maximum loan amount (INR)** Northwind Finance can offer an applicant (target
column `max_loan_offered`). The steps:
- clean the raw data
- engineer credit-policy features and train a regression pipeline
- apply the business rules
- serve the offer through a FastAPI REST API in Docker
- monitor it live (Prometheus + Grafana) and offline (a drift + fairness report)

**Architecture:** see [docs/architecture.md](docs/architecture.md).

## Quick start

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), GNU make, and Docker Desktop for `up`.

```bash
cp .env.example .env      # set your own MODEL_SIGNING_KEY (never commit .env)
make setup                # .venv (Python 3.12) + package with dev extras
make clean-data           # data/raw -> data/processed/*.parquet + data quality report
make train                # train, evaluate, save models/loan_offer_model_vN.pkl + signed .json
make test                 # pytest (warnings are errors)
make docker-build         # API image with the latest model baked in
make up                   # API + Prometheus + Grafana
make simulate-normal      # or simulate-drift / simulate-bad (traffic simulator)
make monitor              # drift + fairness report -> reports/monitoring_report.md/.json
make down
```

Without make: `uv venv --python 3.12 .venv`, then `uv pip install -e ".[dev]"`, then run the
commands from the Makefile by hand. On Windows, set `PYTHONIOENCODING=utf-8` if the console
can't print `₹` (see Troubleshooting).

## URLs (after `make up`)

| Service | URL | Notes |
|---|---|---|
| API docs (Swagger) | <http://localhost:8000/docs> | `/health`, `/ready`, `/model-info`, `/predict`, `/predict/batch`, `/metrics` |
| Prometheus | <http://localhost:9090> | alerts at <http://localhost:9090/alerts> |
| Grafana | <http://localhost:3000> | login **admin / northwind** (`GRAFANA_ADMIN_PASSWORD` in `.env`); dashboard *Northwind Loan Offer API* |

## Business rules

The model gives a raw estimate. `business_rules.py` turns it into the offer, using the
values in `config.CREDIT_POLICY`:

1. **floor_at_zero**: no negative offers.
2. **cap_5x_income**: at most 5 × annual income.
3. **round_down_1000**: round down to the nearest ₹1,000.
4. **No verified income** (missing or ≤ 0): **no offer** (`offered_amount = null`).

**Manual review** sends the application to an underwriter (the offer is still computed) when:
- the income is missing
- the credit score is missing
- the credit score is below 600
- the debt-to-income ratio (existing EMI / monthly income) is above 0.6

## Gender and age: excluded from the model, but monitored

- `gender`, `age`, `marital_status` and `dependents` are protected or sensitive attributes. They are
  **never model inputs** (`features.EXCLUDED_FEATURES`). `requested_amount` is excluded too,
  because of anchoring and leakage risk.
- The API accepts `gender` and `age` only so the system can be **checked for fairness**. They
  are **not written** to the audit log `logs/predictions.jsonl`.
- `make monitor` looks them up by `application_id` in the processed data, a stand-in for a
  separate, access-controlled store. It then compares the offer/income ratio and the
  manual-review rate across gender and age band. Ratios below 0.80 (a rule of thumb borrowed
  from the US "four-fifths" rule) are flagged for review. This is **not a legal test**.
- Leaving a feature out doesn't make a model fair. That is why the outcomes are monitored.

## Responsible use

- **Synthetic data, demo only.** The data, the lender and the policy are invented. Don't use
  this model or its code for real credit decisions.
- **Proxies.** Removing `age` doesn't remove age effects. `years_employed` correlates strongly
  with age and can act as a **proxy** for it, as can other features. Monitor outcomes by
  group rather than relying on the columns you dropped.
- **Personal data.** The prediction log holds personal financial data (income, EMIs, credit
  score, IDs). Under **India's Digital Personal Data Protection (DPDP) Act 2023**, a real system
  would need:
  - informed **consent** for a stated purpose
  - **access control** on the logs and on the protected-attribute store
  - a defined **retention period**, with deletion afterwards
  - the means to honour data-principal rights
- **Fairness screening** here is a heuristic. A real lender needs a documented fairness policy,
  legal review and human oversight of declined or flagged applications.

## Make targets

| Target | What it does |
|---|---|
| `setup` | `.venv` (Python 3.12, uv) + editable install with dev extras |
| `profile` | raw data profile → `reports/data_profile.json` / `.md` (no cleaning) |
| `clean-data` | cleaning → `data/processed/*.parquet` + `reports/data_quality_report.json` |
| `features` | preview the credit-policy features and their correlation with the target |
| `train` | engineered vs baseline pipelines (5-fold CV + 20% test) → `reports/training_report.*`, saves the next model version |
| `models` | list saved model versions |
| `predict-sample` | offers for `data/sample` → `reports/sample_predictions.csv` |
| `test` | pytest (warnings treated as errors) |
| `serve` | run the API locally (`API_HOST` / `API_PORT`, default `0.0.0.0:8000`) |
| `docker-build` | `iomega/northwind-loans-api:0.1.0` + `:latest`, latest model baked in |
| `up` / `down` / `logs` | start / stop the compose stack, follow API logs |
| `simulate-normal` / `simulate-drift` / `simulate-bad` | traffic simulator, 120 s / 300 s / 120 s at 5 rps |
| `reset-logs` | truncate `logs/predictions.jsonl` to 0 bytes |
| `monitor` | drift + fairness report for the last 30 min; **exit 1 if any feature is "investigate"** |
| `check-dashboards` | run every Grafana panel and Prometheus alert query |

⚠️ Pickle files execute code when they're loaded, so **only load models you created yourself** (see [SECURITY.md](SECURITY.md)).

## Components in more detail

### REST API
- Pydantic v2 schemas with `extra="forbid"`. Invalid input → HTTP 422, with the failing field in `detail[].loc`.
- `POST /predict` (one applicant), `POST /predict/batch` (1–1000 applicants).
- One `LoanOfferPredictor` is loaded at start-up; `/ready` returns 503 if no verified model is loaded.

### Observability
- `GET /metrics`: Prometheus metrics (`loan_api_*` traffic / latency / 422s; `loan_model_*`
  predictions, offer and input histograms, reference means, model info). It runs a single
  uvicorn worker on purpose, because metrics are kept in-process.
- Console: one JSON log line per request (`request_id`, `path`, `status_code`, `duration_ms`,
  `model_version`). Send an `X-Request-ID` header, or one is generated.
- `logs/predictions.jsonl`: audit log with one line per applicant (input + output, **no age or gender**).

### Docker
- Multi-stage image (`python:3.12-slim`, uv in the builder), non-root user `app`, no HEALTHCHECK.
- Only the latest model is copied into the image. `.env`, data and tests are excluded.
- The signing key is **not** in the image: compose passes it with `env_file: .env`
  (for a single container: `docker run --env-file .env -p 8000:8000 -v ./logs:/app/logs iomega/northwind-loans-api:0.1.0`).
- `./logs` is bind-mounted. Prometheus and Grafana data live in named volumes.

### Grafana dashboard & alerts
- Dashboard: <http://localhost:3000/d/loan-api/northwind-loan-offer-api> (refresh 5 s). Three rows:
  - service health
  - model behaviour
  - data drift
- Alerts: `LoanApiDown`, `HighServerErrorRate`, `HighLatencyP95`, `IncomeDrift`, `HighManualReviewShare`.
- To reload after editing: `docker compose restart grafana`; `curl -X POST localhost:9090/-/reload`.

### Traffic simulator
`python scripts/simulate_traffic.py --mode {normal,drift,bad,mixed} --rps 5 --duration 120 [--seed 51]`

| Mode | Traffic |
|---|---|
| `normal` | real applicants from `data/processed` |
| `drift` | downturn: income × 0.6, credit score −80, 50% Personal loans |
| `bad` | 30% invalid requests |
| `mixed` | 70% normal / 20% drift / 10% bad |

### Monitoring report
`python -m northwind_loans.monitoring --since-minutes 30 --output reports/monitoring_report`

- **Drift**: PSI of income, credit score, EMI, tenure, DTI and the offered amount. Live
  values are binned with the training decile edges stored in the model metadata.
  - < 0.10: stable
  - 0.10–0.25: watch
  - > 0.25: investigate
- **Loan purpose**: live vs training shares.
- **Fairness screening** by gender and age band (groups with fewer than 30 records are skipped).
- **Volumes**: records, time window, manual-review share.
- A plain-English verdict at the top of the `.md`; `.json` for machines.
- **Exit code 1** when anything is "investigate", so a scheduled job fails. `make` then shows
  `Error 1`, which is expected.

## Troubleshooting

| Problem | Fix |
|---|---|
| `uv` / `make` not found | install uv (`pip install uv`) / GNU make (`choco install make`) |
| `ModuleNotFoundError: northwind_loans` | `make setup`, and use `.venv`'s Python |
| `UnicodeEncodeError ... '₹'` on Windows | `$env:PYTHONIOENCODING="utf-8"` (PowerShell) / `export PYTHONIOENCODING=utf-8` (Git Bash) |
| `/ready` returns 503 / `metadata signature mismatch` | same `MODEL_SIGNING_KEY` as at training, passed via `.env`; or `make train` |
| Docker: `failed to connect to the docker API` | start Docker Desktop |
| Grafana rejects the password | `docker compose exec grafana grafana cli admin reset-admin-password northwind` |
| Panels show "No data" | wait ~15 s after the first traffic (two scrapes are needed) |
| `make monitor` ends with `Error 1` | expected when drift is "investigate"; read `reports/monitoring_report.md` |
| `make monitor` says NO DATA | no predictions in the last 30 min; run a simulator first |

More detail is in [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## More

[Architecture](docs/architecture.md) · [CHANGELOG](CHANGELOG.md) · [TROUBLESHOOTING](TROUBLESHOOTING.md) ·
[CONTRIBUTING](CONTRIBUTING.md) · [SECURITY](SECURITY.md) ·
[CODE OF CONDUCT](CODE_OF_CONDUCT.md) · [LICENSE](LICENSE) (MIT)
