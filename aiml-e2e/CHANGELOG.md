# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `northwind_loans.profiling`: `profile_raw(path)` and CLI that profiles the raw CSV
  (shape, missing values, duplicates, text/numeric columns, date formats,
  out-of-range checks) and writes `reports/data_profile.json` + `.md`. No cleaning.
- `make profile` target.
- `northwind_loans.cleaning`: `parse_money`, `standardize_frame` (row-wise, reusable at
  prediction time) and `clean_applications` (adds de-duplication). CLI writes
  `data/processed/<name>.parquet` and `reports/data_quality_report.json`.
- `make clean-data` target.
- `northwind_loans.features`: stateless `PolicyFeatures` transformer (11 credit-policy
  features, `get_feature_names_out`, `set_output`) and the model column lists
  (`RAW_NUMERIC_INPUTS`, `RAW_CATEGORICAL_INPUTS`, `ENGINEERED_NUMERIC`,
  `MODEL_CATEGORICAL`, `EXCLUDED_FEATURES`).
- `make features` / `python -m northwind_loans.features`: previews the features, the
  policy_amount vs target correlation and a stateless check.
- `northwind_loans.train`: engineered (impute → PolicyFeatures → scale/one-hot →
  LinearRegression) and baseline pipelines, 5-fold shuffled KFold CV + 20% test,
  `train_and_evaluate()` returns the fitted engineered pipeline and report. Writes
  `reports/training_report.json` + `.md`; no model is saved yet.
- `make train` target.
- `northwind_loans.registry`: versioned `save_model` / `load_model` / `list_models`
  (pickle `HIGHEST_PROTOCOL`, SHA-256 of the pickle, HMAC-SHA256-signed metadata,
  sklearn-version warning). `make models` lists versions.
- `northwind_loans.business_rules`: raw prediction -> offer (clip 0, 5x income cap,
  0 without income, round down to 1000).
- `northwind_loans.reference_profile`: `make_bins` (decile edges, `np.unique`,
  `np.searchsorted`, open-ended outer bins), category shares, fairness baseline.
- `MODEL_NAME`, `MODEL_SIGNING_KEY` settings.

- `northwind_loans.predict`: `LoanOfferPredictor` (loads the latest model once;
  `predict_frame` / `predict_one`: standardize_frame -> pipeline -> business rules ->
  manual review). CLI writes `reports/sample_predictions.csv`; `make predict-sample`.
- Business rules: `rules_applied` (floor_at_zero, cap_5x_income, round_down_1000) and
  `review_reasons` (annual_income_missing, credit_score_missing, credit_score_below_600,
  dti_above_0.6).

- FastAPI service (`northwind_loans.api`): Pydantic v2 schemas (`ApplicantIn` with
  `extra="forbid"` and an NWF-035344 example, `OfferOut`, `BatchIn` 1..1000, `BatchOut`);
  `GET /health`, `/ready`, `/model-info`, `POST /predict`, `/predict/batch`. One
  `LoanOfferPredictor` is created in the lifespan handler; title/version come from the
  latest metadata JSON. `make serve` / `python -m northwind_loans.api`.
- `API_HOST`, `API_PORT` settings; `registry.load_metadata()` (JSON only, verified);
  `LoanOfferPredictor.predict_records()`.

- Observability (`northwind_loans.api.observability`): JSON logs (python-json-logger) for
  the app and uvicorn, one request line per call (request_id, method, path, status_code,
  duration_ms, model_version), `X-Request-ID` middleware, 11 Prometheus metrics at
  `GET /metrics`, a `RequestValidationError` handler that counts fields and keeps the
  normal 422 body, and the `logs/predictions.jsonl` audit log without age/gender.
  Single uvicorn worker, uvicorn access log replaced by the middleware line.

- Tests: three `parse_dates` format cases, all 10 sample rows respect the business
  rules, credit score 580 → manual review, batch of 3, key `/metrics` values (113 tests).
- Packaging: multi-stage `Dockerfile` (python:3.12-slim, uv builder, non-root, latest model
  baked in via `MODEL_VERSION`, no HEALTHCHECK), allowlist `.dockerignore`,
  `docker-compose.yml` (api + `prom/prometheus:v3.5.0` + `grafana/grafana:12.1.0`, no
  `version:` key, `./logs` bind mount, named volumes for Prometheus/Grafana data),
  Prometheus scrape config, Grafana datasource provisioning. Image
  `iomega/northwind-loans-api:0.1.0` + `:latest`. Make targets `docker-build`, `up`,
  `down`, `logs`.
- Uvicorn's `color_message` extra is dropped from JSON logs.

- Grafana dashboard `monitoring/grafana/dashboards/loan_api.json` (uid `loan-api`, 3 rows,
  13 panels, refresh 5 s) with file provisioning; Prometheus alert rules
  `monitoring/prometheus/alerts.yml` (group `loan-api`, 5 alerts with summary/description).
- `scripts/check_monitoring.py` / `make check-dashboards`: runs every panel query and alert
  signal against Prometheus. `tests/test_dashboard.py`.
- Known metric label combinations are created at 0 on start-up so `rate()`/`increase()`
  see the first 422s, manual reviews and validation errors.

- `scripts/simulate_traffic.py`: traffic simulator (`--mode normal|drift|bad|mixed`,
  `--rps`, `--duration`, `--seed` = 51, `--data`), paced loop, 5 s timeout, never crashes,
  progress every 10 s and a final summary. Make targets `simulate-normal` (120 s),
  `simulate-drift` (300 s), `simulate-bad` (120 s), `reset-logs`.

- `northwind_loans.monitoring`: offline report from `logs/predictions.jsonl` vs the latest
  model's reference profile - PSI drift (stored decile edges, epsilon 1e-6; stable / watch /
  investigate) for income, credit score, EMI, tenure, DTI and offered amount, loan_purpose
  shares, fairness screening by gender and age band (offer/income and manual-review rate,
  lowest/highest ratio < 0.80 -> review, groups < 30 skipped; gender/age joined by
  `application_id`), volumes. Writes `reports/monitoring_report.md` + `.json`; exit code 1
  on "investigate". `make monitor`.
- `docs/architecture.md`; README completed (quick start, URLs, business rules, responsible use,
  troubleshooting).

### Changed
- `make monitor` now runs the monitoring report; the Prometheus/Grafana query check moved to
  `make check-dashboards`.
- Prometheus: scrape/evaluation every 5 s, `--web.enable-lifecycle` (POST `/-/reload`),
  config directory mounted read-only. Grafana mounts the dashboards folder.
- 4xx/5xx error-rate numerators use `or vector(0)`; `manual_review` label is `"true"`.
- pytest uses a project-local `--basetemp=.pytest_tmp`.
- pytest treats warnings as errors (`filterwarnings = ["error", ...]`), ignoring one
  third-party starlette/anyio deprecation.
- Missing or invalid income now gives **no offer** (NaN / None) instead of 0; rule count
  key renamed to `no_offer_missing_income`. Retrain to refresh the reference profile.
- `python -m northwind_loans.train` now saves the engineered model with metadata;
  report gains in-sample `train` metrics and `reference_profile`.

## [0.1.0] - 2026-10-15

### Added
- Project scaffold: `src/northwind_loans` package (src layout), folders for data,
  models, logs, reports, scripts, tests and monitoring.
- `config.py` with paths, `TARGET`, `CREDIT_POLICY`, `VALID_RANGES`,
  `INCOME_PAISE_THRESHOLD`; `.env` support via python-dotenv.
- `pyproject.toml` with pinned dependencies and a `dev` extra.
- Makefile (`setup`, `test` working; other targets are placeholders).
- README, troubleshooting, contributing, security, code of conduct, MIT license.
