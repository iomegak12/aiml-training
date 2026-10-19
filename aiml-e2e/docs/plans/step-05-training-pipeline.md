# Step 5 — Training Pipeline (plan & outcome)

## Context
Steps 3–4 produced clean data (`data/processed/*.parquet`, 55,000 rows) and a stateless
`PolicyFeatures` transformer. `policy_amount` alone correlates 0.99 with the target.
Step 5 trains two LinearRegression pipelines and compares them, to show how much the policy features help:
- **Engineered:** the production candidate.
- **Baseline:** raw inputs only.

It returns the fitted engineered pipeline and the metrics, but **saves no model**; that is Step 6.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Coefficients | Console prints the top 8 by \|coef\| plus the intercept; the reports list all 20 |
| OneHotEncoder | `drop="first"`, `handle_unknown="ignore"`, `sparse_output=False`, which avoids the dummy-variable trap |
| Metrics | R², RMSE, MAE (INR); CV shows mean ± std |
| Test set (20%) | Both pipelines fit on the full 80% and score the test set once, for reporting only |
| Target | Drop missing targets (220, reported); **keep** zero targets (76, reported) |
| Baseline | Same imputer → StandardScaler (raw numerics) + OHE (raw categoricals) → LinearRegression; no PolicyFeatures |
| API | `train_and_evaluate(data_dir) -> (engineered_pipeline, report)`; the CLI writes only the two reports |

## Pipelines (`src/northwind_loans/train.py`)
```
engineered: impute ─► features (PolicyFeatures) ─► preprocess ─► LinearRegression
baseline  : impute ───────────────────────────────► preprocess ─► LinearRegression

impute     = ColumnTransformer(median on RAW_NUMERIC_INPUTS,
                               most_frequent on RAW_CATEGORICAL_INPUTS,
                               verbose_feature_names_out=False).set_output("pandas")
preprocess = ColumnTransformer(StandardScaler on numerics,
                               OneHotEncoder(drop="first", handle_unknown="ignore") on categoricals)
  engineered: numerics = RAW_NUMERIC_INPUTS + ENGINEERED_NUMERIC; categoricals = MODEL_CATEGORICAL
  baseline  : numerics = RAW_NUMERIC_INPUTS;                      categoricals = RAW_CATEGORICAL_INPUTS
```
- **Evaluation:** `KFold(5, shuffle=True, random_state=51)` with `cross_validate` on the training set.
- **Split:** `train_test_split(test_size=0.2, random_state=51)`.

Functions:
- data: `load_processed`, `drop_missing_target`, `split`
- pipelines: `make_imputer`, `make_preprocessor`, `make_engineered_pipeline`, `make_baseline_pipeline`
- evaluation: `cross_validate_pipeline`, `test_metrics`, `coefficients` (also returns the one-hot reference categories)
- `train_and_evaluate`
- output: `write_reports`, `print_comparison`, `main`

Outputs: `reports/training_report.json` and `reports/training_report.md`. `make train` runs the CLI.

## Tests: `tests/test_train.py` (5 tests, 400 synthetic rows, target ≈ policy_amount × noise)
- Missing targets are dropped and counted; the 80/20 split sizes are right.
- The return value is a fitted 4-step Pipeline that predicts finite values.
- Metric keys exist, RMSE is positive, and engineered R² > baseline R².
- 20 coefficients line up with `coef_`, sorted by |coef|, with reference categories present.
- The CLI writes both reports and nothing to `models/`.

## Outcome (2026-10-15)
- Data: 55,000 loaded, 220 missing targets dropped, 76 zero targets kept, train 43,824 / test 10,956.

| Pipeline | CV R² | CV RMSE (INR) | CV MAE (INR) | Test R² | Test RMSE | Test MAE |
|---|---|---|---|---|---|---|
| engineered | 0.9784 ± 0.0043 | 328,646 ± 28,979 | 157,193 ± 1,538 | 0.9785 | 321,783 | 158,482 |
| baseline | 0.7543 ± 0.0032 | 1,115,359 ± 15,320 | 676,003 ± 4,560 | 0.7518 | 1,094,070 | 667,633 |

- Policy features cut RMSE about 3.4× and MAE about 4.3×. The CV and test scores agree, so there is no sign of overfitting.
- Top coefficient: `policy_amount` (+27.2 L per standard deviation). The collinear engineered features (`affordable_amount`, `emi_capacity_amount`, `policy_cap`) offset each other, so read them as a group.
- One-hot reference categories are `Business Owner`, `Auto` and **`600-649`**. `<600` is not first because string sorting puts `<` after the digits.
- `models/` still holds only `.gitkeep`; the full suite passes (53 tests, `-W error`).

## Not in this step
Saving the model or metrics, hyper-parameter tuning, other model types, prediction CLI, API.
