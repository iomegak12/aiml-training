# Step 5 — Training Pipeline (no model saving)

## Context
Steps 3–4 produced clean data (`data/processed/*.parquet`, 55,000 rows) and a stateless
`PolicyFeatures` transformer. `policy_amount` alone correlates 0.99 with the target.
Step 5 trains and compares two LinearRegression pipelines to show how much the policy features help:
- **Engineered:** the production candidate.
- **Baseline:** raw inputs only.

It returns the fitted engineered pipeline and the metrics, but **saves no model**; that is Step 6.

## Decisions (agreed with Ram)
- **Coefficients:** the console prints the top 8 by |coef| (feature names + intercept). The reports list all 20.
- **OneHotEncoder:** `drop="first"`, `handle_unknown="ignore"`, `sparse_output=False`. This avoids the dummy-variable trap so coefficients are readable. Verified to work in sklearn 1.5.2.
- **Metrics:** R², RMSE, MAE (INR). CV shows mean ± std.
- **Test set (20%):** after CV, fit on the full 80% train and score the test set once, for reporting only.
- **Target:** drop missing targets (220) and report the count. **Keep** zero targets (76) and report the count.
- **Baseline:** same imputer → StandardScaler (raw numerics) + OHE (raw categoricals) → LinearRegression, without PolicyFeatures.
- **API:** `train_and_evaluate(data_dir) -> (engineered_pipeline, report)`. The CLI writes only the 2 reports.

## File: `src/northwind_loans/train.py`
Reuses `features.PolicyFeatures`, `RAW_NUMERIC_INPUTS`, `RAW_CATEGORICAL_INPUTS`, `ENGINEERED_NUMERIC`, `MODEL_CATEGORICAL`,
and `config.TARGET`, `RANDOM_STATE`, `PROCESSED_DATA`, `REPORTS_DIR`, `LOG_LEVEL`.

Constants: `TEST_SIZE = 0.2`, `CV_FOLDS = 5`, `SCORING = {"r2", "neg_root_mean_squared_error", "neg_mean_absolute_error"}`.

| Function | Purpose |
|---|---|
| `load_processed(data_dir)` | concatenate every `*.parquet` |
| `drop_missing_target(df) -> (df, dropped)` | drop rows with no target |
| `split(df)` | `train_test_split(test_size=0.2, random_state=RANDOM_STATE)` |
| `make_imputer()` | details below |
| `make_engineered_pipeline()` | details below |
| `make_baseline_pipeline()` | details below |
| `cross_validate_pipeline(pipe, X, y)` | `KFold(5, shuffle=True, random_state=RANDOM_STATE)` + `cross_validate`; returns {metric: {mean, std}} with signs flipped back to positive RMSE/MAE |
| `test_metrics(pipe, X_test, y_test)` | {r2, rmse, mae} |
| `coefficients(pipe)` | names from `preprocess.get_feature_names_out()` plus `model.coef_`, sorted by \|coef\|; also the intercept |
| `train_and_evaluate(data_dir=PROCESSED_DATA) -> (Pipeline, dict)` | runs everything above |
| `write_reports(report, out_dir)` | writes `reports/training_report.json` + `.md` |
| `print_comparison(report)` | prints the comparison table |
| `main(argv=None)` | CLI |

`make_imputer()` is a ColumnTransformer:
- median `SimpleImputer` on `RAW_NUMERIC_INPUTS`
- most_frequent `SimpleImputer` on `RAW_CATEGORICAL_INPUTS`
- `verbose_feature_names_out=False`, `.set_output(transform="pandas")`, so the original column names are kept

`make_engineered_pipeline()` steps:
1. `impute`: `make_imputer()`
2. `features`: `PolicyFeatures()`
3. `preprocess`: ColumnTransformer with StandardScaler on `RAW_NUMERIC_INPUTS + ENGINEERED_NUMERIC` and OHE on `MODEL_CATEGORICAL`, `verbose_feature_names_out=False`
4. `model`: `LinearRegression()`

`make_baseline_pipeline()` steps:
1. `impute`
2. `preprocess`: StandardScaler on `RAW_NUMERIC_INPUTS` and OHE on `RAW_CATEGORICAL_INPUTS`
3. `model`: `LinearRegression()`

Report contents:
- `data`: rows_loaded, target_missing_dropped, target_zero_kept, train_rows, test_rows
- `settings`: test_size, cv_folds, shuffle, random_state
- `cv` and `test` for each pipeline
- `engineered_coefficients`: intercept + full list

CLI: `python -m northwind_loans.train [--data-dir] [--report-dir]` prints:
- the data counts
- the comparison table: Pipeline | CV R² | CV RMSE | CV MAE | Test R² | Test RMSE | Test MAE
- the top 8 coefficients

## Other edits
- `Makefile`: `train` runs `$(PY) -m northwind_loans.train`.
- `tests/test_train.py`: about 400 synthetic rows where the target is roughly `policy_amount` × noise (`random_state=51`), written to a tmp parquet. Assert:
  - missing targets are dropped and counted
  - the return value is a fitted Pipeline that can `predict`
  - the metric keys exist
  - engineered R² > baseline R²
  - coefficient names line up with `coef_`
  - the CLI writes both reports and nothing to `models/`
- README, CHANGELOG, and `docs/plans/step-05-training-pipeline.md` (reference copy of this plan, as in Step 4).

## Verification (show real output)
1. `make train`: shows the data counts, comparison table and top 8 coefficients.
2. Check that `reports/training_report.{json,md}` exist and that `models/` holds only `.gitkeep`.
3. `pytest -q -W error`: all tests pass, old and new.

Talking point for participants: the engineered numerics are strongly collinear (`affordable_amount` ≈ `policy_amount`), so their individual coefficients can be large with opposite signs. Read them as a group.
