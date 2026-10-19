# Step 7 — Prediction Pipeline + Business Rules

## Context
Step 6 saves signed, versioned models (v1, v2). Step 7 turns a saved model into offers for new applicants:
1. Clean raw rows with the **same** `standardize_frame` used in training (no de-duplication).
2. Run the pipeline.
3. Apply the business rules and manual-review flags.

`LoanOfferPredictor` will be reused by the API later.
Sample file: 10 rows, one with no credit score (NWF-039077) and one with no actual target (NWF-030496).

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Missing/invalid income | `apply_business_rules` returns **NaN** (no offer) instead of 0 → `offered_amount = None`, `raw_model_estimate = None`, reason `annual_income_missing`, manual_review True. Re-run `make train` → **v3**, so the reference profile excludes these rows. |
| Offer when flagged | Still computed and returned; `manual_review = True` with reasons |
| `rules_applied` | Only the rules that changed the amount: `floor_at_zero`, `cap_5x_income`, `round_down_1000` |
| `raw_model_estimate` | Nearest rupee, int (can be negative) |
| Reasons | snake_case codes: `annual_income_missing`, `credit_score_missing`, `credit_score_below_600`, `dti_above_0.6`; thresholds from `CREDIT_POLICY["manual_review_rules"]` |
| dti missing | No flag (as specified) |
| CLI paths | `--input` defaults to `SAMPLE_DATA`, `--output` to `reports/sample_predictions.csv`; lists joined with `"; "` |
| predict_frame output | Only the 7 output columns, in input row order |

## Changes

### `business_rules.py` (extend)
- `apply_business_rules`: missing or ≤ 0 income → NaN (was 0).
- Rule-name constants, built from the policy:
  - `FLOOR_AT_ZERO = "floor_at_zero"`
  - `CAP_RULE = f"cap_{absolute_cap_income_multiple}x_income"` → `cap_5x_income`
  - `ROUND_RULE = f"round_down_{round_offer_to}"` → `round_down_1000`
- `rules_applied(raw, X) -> list[list[str]]`, per row:
  - `floor_at_zero` if raw < 0
  - `cap_5x_income` if raw > cap
  - `round_down_1000` if the clipped/capped value wasn't already a multiple of 1000
  - `[]` when there is no income
- `review_reasons(X_clean, dti) -> list[list[str]]`: income missing, credit score missing, credit score < 600, dti > 0.6.
- `count_rule_hits`: key `zero_for_missing_income` → `no_offer_missing_income`.

### `src/northwind_loans/predict.py` (new)
```python
OUTPUT_COLUMNS = ["application_id", "offered_amount", "raw_model_estimate", "manual_review",
                  "review_reasons", "rules_applied", "model_version"]

class LoanOfferPredictor:
    def __init__(self, version=None, model_dir=MODEL_DIR)
    def predict_frame(self, df) -> pd.DataFrame
    def predict_one(self, record: dict) -> dict
```
- `__init__`: `registry.load_model(...)` runs once (latest by default) and keeps `pipeline`, `metadata`, `model_version`.
- `predict_frame(df)`:
  1. `cleaning.standardize_frame(df)`.
  2. Add any missing raw input columns as NaN (object dtype for categoricals).
  3. `pipeline.predict`, `apply_business_rules`, and dti via `PolicyFeatures` on the cleaned, **un-imputed** rows.
  4. `review_reasons`, `rules_applied`.
  5. Return the 7 columns; amounts are nullable `Int64`.
- `predict_one(record)`: wraps `predict_frame` and returns plain Python types (int/None, bool, list), ready for JSON later.
- CLI: `python -m northwind_loans.predict [--input] [--output] [--version]`.
  - Reads with `profiling.read_raw_csv` (strings, same as training) and writes the CSV.
  - Prints a table: application_id | actual max_loan_offered (if present) | offered | % diff | manual review | reasons.

### Other
- `Makefile`: `predict-sample` runs `$(PY) -m northwind_loans.predict`.
- `reference_profile.py` needs no change. NaN offers are dropped by `numeric_summary`, and the rule counts get the renamed key.
- Tests:
  - `test_business_rules.py`: update for NaN and the renamed key; add `rules_applied` and `review_reasons` cases.
  - `test_predict.py`:
    - module fixture: train on synthetic data (`tests.test_train.make_processed`), then `save_model` into a tmp dir
    - raw string records covering: normal; `Rs. 5,00,000` income; missing score; score 550; high EMI (dti > 0.6); missing income → None
    - check: offers are None or within [0, 5× income] and divisible by 1000; output columns and order; `predict_one` types; `model_version`
- README, CHANGELOG, `docs/plans/step-07-prediction-pipeline.md`.

## Verification (show real output)
1. `make train`: saves v3 with the updated profile.
2. `make predict-sample`: prints the table and writes `reports/sample_predictions.csv`.
3. Script asserts every `offered_amount` is None, or `0 ≤ offer ≤ 5 × income` and `offer % 1000 == 0` (income from `standardize_frame` of the sample).
4. `pytest -q -W error`: all tests pass.
