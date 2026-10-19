# Step 15 — Drift & Fairness Monitoring Report (+ README finish)

## Context
The traffic simulator (Step 14) fills `logs/predictions.jsonl`. Ram now wants an offline report that compares live traffic with the training reference profile stored in the latest model metadata (Step 6). It covers:
- drift (PSI)
- fairness screening (gender / age band)
- volumes

The report is written as Markdown + JSON. The exit code is 1 when anything needs investigation, so it can fail a scheduled job. The README is completed in this step as well.

Read-only findings:
- Audit line: `{timestamp (UTC ISO), request_id, endpoint, model_version, input{…, application_id}, output{offered_amount, manual_review, review_reasons, …}}`. There is no age or gender (PII rule).
- v4 `reference_profile.numeric` has `bin_edges` / `bin_shares` for all six features. Note that `dti` and `monthly_existing_emi` have duplicated edges collapsed, giving 8 bins. `categorical.loan_purpose` holds the shares.
- Reference dti = `monthly_existing_emi / (annual_income / 12)` (`features.py:138`).
- `data/processed/loan_applications_raw.parquet`: `application_id` is unique (55,000 rows), with gender and age present.
- `docs/architecture.md` doesn't exist yet. `make monitor` is already used by `scripts/check_monitoring.py`.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Fairness attributes | Join by `application_id` to the processed data (`--data` flag). The log stays PII-free. Records that don't match are counted and excluded from fairness. |
| Make target | `make monitor` runs the new report; the old query check becomes `make check-dashboards` |
| Architecture | Create a short `docs/architecture.md` (ASCII diagram + one line per component) |

## New: `src/northwind_loans/monitoring.py` (logging inside; the CLI prints a short summary)
Constants:
- `PSI_EPSILON = 1e-6`
- `PSI_WATCH = 0.10`, `PSI_INVESTIGATE = 0.25`
- `FAIRNESS_THRESHOLD = 0.80`, `MIN_GROUP_SIZE = 30`
- `DRIFT_FEATURES`: annual_income, credit_score, monthly_existing_emi, requested_tenure_months, dti, and offered_amount, which is compared against the reference `predicted_offer`

| Function | Purpose |
|---|---|
| `read_prediction_log(path, since_minutes=None, now=None) -> pd.DataFrame` | parse JSONL; flatten `input.*` + `output.*` into one row per record; filter by `timestamp >= now - since` |
| `add_dti(df)` | `monthly_existing_emi / (annual_income/12)`, NaN when income ≤ 0 |
| `psi(expected_shares, actual_shares) -> float` | `Σ (a−e)·ln(a/e)`, both clipped at 1e-6 |
| `psi_status(value) -> str` | stable / watch / investigate |
| `numeric_drift(df, reference_numeric) -> list[dict]` | reuses `reference_profile.make_bins(values, edges=stored_edges)`; reports feature, PSI, status, live mean vs reference mean, n |
| `category_drift(df, reference_shares) -> dict` | loan_purpose live vs reference share per category, plus PSI and status, aligned on all categories (unseen categories get 0 → epsilon) |
| `attach_protected_attributes(df, data_path)` | left-join gender and age by application_id; returns df + matched count |
| `group_ratio(values_by_group) -> dict` | groups with ≥ 30 records only; min/max ratio; `"review"` if < 0.80, else `"ok"`; ratio None when < 2 groups or max is 0 |
| `fairness_report(df) -> dict` | for gender and age_band (via `reference_profile.age_band`): (a) mean offered_amount/annual_income, (b) manual-review rate; group sizes and the skipped groups are listed |
| `volumes(df) -> dict` | records, first/last timestamp, manual-review share |
| `build_report(log_path, model_dir, data_path, since_minutes) -> dict` | loads the latest metadata via `registry.load_metadata()` (JSON only, no pickle); verdict: investigate / watch / stable |
| `to_markdown(report) -> str` | plain-English verdict at the top, then tables: volumes, drift, loan_purpose shares, fairness (with the four-fifths rule-of-thumb note: a screening heuristic, not a legal test) |
| `write_report(report, output)` | `output.with_suffix(".md")` / `.json` |
| `main(argv) -> int` | args `--since-minutes`, `--output` (default `REPORTS_DIR/"monitoring_report"`), `--log`, `--data`; prints the verdict + paths; `sys.exit(1)` if any feature (numeric or loan_purpose) is "investigate" |

Edge cases:
- An empty or missing log, or no records in the window, gives a report with verdict "no data", exit 0, and a logged warning.
- Offer ratio: rows where offered_amount is None or income ≤ 0 are left out.

## Makefile
- `monitor`: `$(PY) -m northwind_loans.monitoring --since-minutes 30 --output reports/monitoring_report`
- `check-dashboards`: the old echo URLs + `scripts/check_monitoring.py`
- Update `.PHONY` and help.

## Tests: `tests/test_monitoring.py` (synthetic data, tmp paths, uses `trained_model_dir`)
- `psi`: identical shares → 0; an empty bin doesn't produce inf (epsilon); status thresholds at 0.10 / 0.25.
- `read_prediction_log`: flattening, `since_minutes` filtering with a fixed `now`.
- `numeric_drift`: values drawn from the same edges → stable; income × 0.6 → investigate.
- `group_ratio`: groups under 30 are skipped; ratio 0.7 → review; a single group → None.
- `main` writes .md + .json; exit code is 0 for stable data and 1 for drifted data; an empty log gives exit 0.

## Docs
- **README** (restructured):
  - goal and disclaimer
  - architecture link
  - quick start: setup, clean-data, train, test, up, simulate-*, monitor, down
  - URLs: 8000/docs, 9090, 3000 admin/northwind
  - business rules
  - gender/age excluded from the model but monitored
  - a **Responsible use** section: synthetic data; years_employed can act as a proxy for age; the log holds personal data that would need consent, access control and retention under India's DPDP Act 2023
  - troubleshooting (short, linking to TROUBLESHOOTING.md)
- New `docs/architecture.md`.
- CHANGELOG.
- `docs/plans/step-15-monitoring-report.md`.

## Verification (show real output)
1. `make test`: all pass.
2. `make reset-logs` → `simulate_traffic.py --mode normal --duration 60` → `make monitor`: expect exit 0, all stable.
3. `make reset-logs` → `--mode drift --duration 60` → `make monitor`: expect exit 1, with income and credit_score "investigate".
4. Show the verdict and fairness tables from `reports/monitoring_report.md`.

Expected numbers:
- Normal: about 300 records; PSI noise ≈ 9/300 ≈ 0.03, so stable.
- Drift: income and score PSI well above 0.25. dti and offered_amount will probably investigate as well; loan_purpose PSI ≈ 0.2, so "watch".
- Gender "Other" (about 1%) and probably age 50+ will be skipped (< 30 records).
