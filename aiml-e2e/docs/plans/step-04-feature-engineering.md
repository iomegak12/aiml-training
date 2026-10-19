# Step 4 — Feature Engineering (plan & outcome)

## Context
Step 3 produced typed, standardised data in `data/processed/loan_applications_raw.parquet`
(55,000 rows; missing values left as NaN, nothing imputed).
Step 4 turns Northwind's credit policy (`config.CREDIT_POLICY`) into model features.
They come from a **stateless** scikit-learn transformer that can sit inside the
training pipeline and be reused unchanged at prediction time.
It also fixes the column lists the model will use, and records why the other columns are excluded.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| What `fit()` does | Records only `feature_names_in_` / `n_features_in_` (column names) and returns `self`. It learns nothing from values. `transform()` also works without `fit()`. |
| Missing inputs | NaN propagates (e.g. no `credit_score` → no band → `policy_amount` NaN). No imputation here; a pipeline imputer handles it later. |
| `credit_haircut` | Follows the spec exactly: `credit_haircut.get(band, 1.0)`. |
| Rounding | `policy_amount` stays continuous. Rounding to `round_offer_to` (1000) belongs to the final offer at prediction time. |
| Validation | Non-DataFrame input → `TypeError`; missing required column → `ValueError("missing required columns: [...]")`. |
| FOIR bonus | Only when `employment_type == "Salaried"`. A missing or any other value gets no bonus. |
| Unknown `loan_purpose` | No rate or cap → NaN, the same as any missing input. |
| Zero/negative income | `dti` is NaN, not `inf`. |

## File: `src/northwind_loans/features.py`

### Transformer: `PolicyFeatures(TransformerMixin, BaseEstimator)`
- `__init__(policy=None)`: `None` means `config.CREDIT_POLICY`. Storing the policy as a parameter keeps `clone()` working.
- `fit(X, y=None)`: validates the input, records the column names, returns `self`.
- `transform(X)`: returns a copy of `X` with every original column plus the 11 new ones.
- `get_feature_names_out(input_features=None)`: input names followed by `NEW_FEATURES`.
- `set_output(transform="pandas")`: comes from `TransformerMixin`, because `get_feature_names_out` exists.

### New columns (in output order)
| # | Column | Formula |
|---|---|---|
| 1 | `monthly_income` | `annual_income / 12` |
| 2 | `dti` | `monthly_existing_emi / monthly_income` (NaN if income ≤ 0) |
| 3 | `credit_band` | `<600`, `600-649`, `650-699`, `700-749`, `750+` (left-inclusive: 600 → `600-649`, 750 → `750+`) |
| 4 | `foir_limit` | `foir_by_credit_band[band]` + `salaried_foir_bonus` if Salaried |
| 5 | `affordable_emi` | `max(monthly_income × foir_limit − monthly_existing_emi, 0)` |
| 6 | `annuity_factor` | `(1 − (1 + r)^−n) / r`, with `r = rate_card_pct[purpose] / 1200` and `n = requested_tenure_months` |
| 7 | `emi_capacity_amount` | `affordable_emi × annuity_factor` |
| 8 | `policy_cap` | `income_multiple_cap[purpose] × annual_income` |
| 9 | `affordable_amount` | `min(emi_capacity_amount, policy_cap, absolute_cap_income_multiple × annual_income)` (NaN if any term is NaN) |
| 10 | `credit_haircut` | `credit_haircut.get(band, 1.0)` |
| 11 | `policy_amount` | `affordable_amount × credit_haircut` |

Helpers: `credit_band(score)` uses `pd.cut`, `annuity_factor(rate_pct, months)`, and `_as_float(series)` turns nullable Int64 into float64.
Constants: `REQUIRED_INPUTS`, `CREDIT_BANDS`, `NEW_FEATURES`.

### Model column lists (imported by later steps)
```python
RAW_NUMERIC_INPUTS     = ["annual_income", "monthly_existing_emi", "credit_score",
                          "requested_tenure_months", "years_employed"]
RAW_CATEGORICAL_INPUTS = ["employment_type", "loan_purpose"]
ENGINEERED_NUMERIC     = ["dti", "emi_capacity_amount", "policy_cap",
                          "affordable_amount", "policy_amount"]
MODEL_CATEGORICAL      = ["employment_type", "loan_purpose", "credit_band"]
```
`EXCLUDED_FEATURES` (column → reason):
- `requested_amount`: anchoring and leakage risk; the offer must reflect capacity, not the ask
- `gender`, `age`, `marital_status`, `dependents`: protected or proxy attributes; monitored for fairness, never used
- `city`, `education`: possible proxies; excluded in v1
- `application_id`, `application_date`: identifiers

## Tests: `tests/test_features.py` (17 tests)
- **Worked by hand, salaried Home loan (score 760):**
  - FOIR 0.55 + 0.05 = 0.60
  - affordable EMI ₹50,000
  - EMI capacity is the binding limit
  - no haircut
- **Worked by hand, self-employed Personal loan (score 610):**
  - FOIR 0.40
  - EMI capacity (≈ ₹4.48 L) is lower than the 1.5× income cap
  - 0.8 haircut
- **Missing credit score:** band, FOIR and `policy_amount` all come out NaN.
- **Credit-band edges:** 300, 599, 600, 649, 650, 749, 750, 900.
- **Zero income:** `dti` is NaN.
- **Columns:** the original columns are kept, the input frame is not modified, and the new columns come out in `NEW_FEATURES` order.
- **Stateless:**
  - `fit` returns `self`
  - repeated transforms are equal
  - fitting on other data changes nothing
  - `clone()` gives the same output
- **Feature names:** `get_feature_names_out` matches the output columns, and `set_output(transform="pandas")` works.
- **Errors:** clear `ValueError` / `TypeError`.
- **Exclusions:** the model column lists don't overlap `EXCLUDED_FEATURES`.

## Acceptance checks (run on `data/processed/loan_applications_raw.parquet`)
1. Transform the first 5 rows and print the input columns plus `policy_amount`, `dti`, `affordable_emi` and `affordable_amount`.
2. On rows where all inputs and the target are present, print the correlation between `policy_amount` and `max_loan_offered`.
3. Call `transform` 3 times and after re-fitting on other data; the outputs must be identical.

## Outcome (2026-10-15)
- Full suite: **47 passed** (`pytest -W error`).
- Correlation on **50,243 / 55,000** complete rows: Pearson **0.9911**, Spearman **0.9920**. The policy formula alone explains most of the offer; the model learns where the credit team departs from it.
- Stateless: run1 == run2 == run3, and the output is still identical after re-fitting on 100 random rows (`random_state=51`). The only stored attributes are `feature_names_in_` and `n_features_in_`.
- Output: 30 columns, the 19 original plus 11 new.
- A test caught a wrong expectation of mine, not a code bug: in the Personal-loan case the EMI capacity binds, not the income cap.

## Follow-up: `make features`
Added after the step at Ram's request.
- `python -m northwind_loans.features [--input PATH]` (default `data/processed/loan_applications_raw.parquet`) prints the 3 acceptance checks above.
- `policy_target_correlation()` is a small helper.
- One CLI test brings the suite to **48 passed**.

## Not in this step
Imputation, encoding, model training and rounding of the offer all belong to later steps.
