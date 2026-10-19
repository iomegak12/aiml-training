# Step 7 — Prediction Pipeline + Business Rules (plan & outcome)

## Context
Step 6 saves signed, versioned models. Step 7 turns the latest saved model into offers for new applicants:
1. Clean with the **same** `standardize_frame` as training (no de-duplication).
2. Run the pipeline.
3. Apply the business rules, then the manual-review flags.

`LoanOfferPredictor` is what the API will reuse.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Missing/invalid income | No offer: `offered_amount = None`, `raw_model_estimate = None`, reason `annual_income_missing`, manual_review True. `apply_business_rules` now returns NaN instead of 0; retrained so the reference profile excludes these rows. |
| Offer when flagged | Still computed and returned; `manual_review = True` with reasons |
| `rules_applied` | Only rules that changed the amount: `floor_at_zero`, `cap_5x_income`, `round_down_1000` (names built from `CREDIT_POLICY`) |
| `raw_model_estimate` | Nearest rupee, int |
| Reason codes | `annual_income_missing`, `credit_score_missing`, `credit_score_below_600`, `dti_above_0.6` (from `manual_review_rules`) |
| dti missing | No flag (as specified) |
| CLI | `--input` defaults to `data/sample/sample_applicants.csv`, `--output` to `reports/sample_predictions.csv`; also `--version`, `--model-dir`; lists joined with `"; "` |
| `predict_frame` output | The 7 columns, in input order |

## Modules
- **`business_rules.py`**:
  - `apply_business_rules` (NaN without income), `rules_applied`, `review_reasons`, `count_rule_hits`
  - rule/reason constants built from the policy
  - review uses the cleaned, **un-imputed** values, so a missing score is visible. Otherwise the model's median-imputed score could give a thin-file applicant a prime offer.
- **`predict.py`**: `LoanOfferPredictor(version=None, model_dir=MODEL_DIR)`.
  - It loads once via `registry.load_model`.
  - `predict_frame(df)`: `standardize_frame` → add any absent input columns as NaN → `pipeline.predict` → rules → dti via `PolicyFeatures` on un-imputed rows → reasons.
  - `predict_one(record)` returns plain Python types.
  - CLI helpers: `comparison_table`, `write_predictions`, `main`.
- **`Makefile`**: `predict-sample` runs `python -m northwind_loans.predict`.

Output columns: `application_id`, `offered_amount`, `raw_model_estimate`, `manual_review`, `review_reasons`, `rules_applied`, `model_version`.

## Tests (full suite 77 passed, `-W error`)
- **`test_business_rules.py`**:
  - rule names; floor, round down, cap; NaN without income
  - `rules_applied` per row
  - review reasons, including the boundaries (score 600 and dti 0.6 are not flagged)
  - rule counts
- **`test_predict.py`** (model trained on synthetic data in a tmp dir):
  - output columns, order and cleaned IDs
  - offers within [0, 5× income] and divisible by 1000
  - each review reason; flagged rows still get offers
  - missing income → None
  - `predict_one` returns plain types and handles missing keys
  - the CLI writes the CSV

## Outcome (2026-10-15)
- `make train` saved **v4**. v3 already existed from a `make train` run between steps. v4's profile excludes the 373 no-income rows (`predicted_offer` count 43,451) and counts `clipped_to_zero` only where income is valid (107).
- `make predict-sample` (10 applicants, model v4):

| application_id | actual | offered | diff % | review |
|---|---|---|---|---|
| NWF-035344 | 4,923,000 | 4,583,000 | −6.9 | |
| NWF-003600 | 4,966,000 | 4,542,000 | −8.5 | |
| NWF-004371 | 1,664,000 | 1,569,000 | −5.7 | |
| NWF-022976 | 207,000 | 158,000 | −23.7 | |
| NWF-039077 | 297,000 | 242,000 | −18.5 | YES: credit_score_missing |
| NWF-033555 | 2,474,000 | 2,449,000 | −1.0 | |
| NWF-008097 | 2,033,000 | 2,071,000 | +1.9 | |
| NWF-054663 | 806,000 | 806,000 | 0.0 | |
| NWF-013391 | 1,190,000 | 1,180,000 | −0.8 | |
| NWF-030496 | — | 976,000 | — | |

- Assertion: every offer is None, or 0 ≤ offer ≤ 5× income and divisible by 1000 → **OK**. Only `round_down_1000` fired on this sample.

## Not in this step
API, Docker, monitoring and drift/PSI.
