# Step 15 — Drift & Fairness Monitoring Report (plan & outcome)

## Context
The simulator (Step 14) fills `logs/predictions.jsonl`. This step adds an offline report that
compares live traffic with the reference profile in the latest model metadata (Step 6). It covers:
- drift (PSI)
- fairness screening
- volumes

The report is written as Markdown + JSON, with exit code 1 on "investigate". The README is completed too.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Fairness attributes | The audit log has no age or gender (PII). They are joined by `application_id` from `data/processed` (`--data`), a stand-in for a separate access-controlled store; unmatched rows are counted |
| Make target | `make monitor` = this report; the old Prometheus/Grafana query check becomes `make check-dashboards` |
| Architecture | New short `docs/architecture.md` (ASCII diagram + component table) |

## `src/northwind_loans/monitoring.py`
- **Reading the log**:
  - `read_prediction_log`: flattens `input` + `output`; `--since-minutes` filter on the UTC timestamp
  - `add_dti`: EMI / (income / 12), the same formula as training
- **`attach_protected_attributes`**: left join of `gender` and `age` by `application_id`.
- **Drift**:
  - `psi` (shares clipped at 1e-6) and `psi_status`: < 0.10 stable, 0.10–0.25 watch, > 0.25 investigate
  - `numeric_drift` reuses `reference_profile.make_bins(values, edges=stored_edges)`; `offered_amount` is compared with the reference `predicted_offer`
  - `category_drift`: loan_purpose shares plus PSI; unseen categories are included
- **Fairness**:
  - `group_ratio`: groups with ≥ 30 records; lowest/highest ratio; < 0.80 → review
  - `fairness_report`: offer/income and manual-review rate, by gender and by age band (`reference_profile.age_band`)
- **Output**:
  - `volumes`, `build_report` (metadata JSON only, no pickle), `verdict_text`
  - `to_markdown`, `write_report`, `exit_code`, `main`
- An empty log or window gives "no data" and exit 0.

## Tests: `tests/test_monitoring.py` (19 tests; full suite 157 passed)
- PSI: identical → 0; an empty bin stays finite; thresholds.
- Numeric drift: income × 0.6 → investigate.
- Category drift: an unseen category is included.
- Log: flattening, the `since` filter, a missing file.
- `group_ratio`: small groups are skipped; flags review / ok / not enough data.
- CLI on synthetic traffic written by the real `log_predictions`: stable → 0, drifted → 1, empty → 0. The audit log still has no PII.

## Outcome (2026-10-16, compose stack, model v4)
| Run | Records | Result |
|---|---|---|
| normal 60 s | 300 | **STABLE**, exit 0. PSI income 0.032, score 0.064, EMI 0.013, tenure 0.020, dti 0.032, offer 0.010, purpose 0.007 |
| drift 60 s | 300 | **INVESTIGATE**, exit 1. PSI income 0.78, score 1.48, dti 0.87, offer 2.25; EMI/tenure stable; loan_purpose 0.137 watch (Personal 46% vs 28%) |

- In the normal run, fairness flagged **manual-review rate** for gender (0.47) and age band
  (0.14). The review rates are small (1–9%, i.e. a handful of cases per group), so these are
  small-number noise. This is exactly why the rule is "screening, not a legal test". The
  offer/income ratios were all ≥ 0.88.
- `make monitor` prints `Error 1` and the shell sees exit 2 (make's own code). The module itself returns 1.

## Not in this step
Scheduling the job, alert routing, retraining.
