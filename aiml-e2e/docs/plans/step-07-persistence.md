# Step 6 — Model Persistence with Signed Metadata

## Context
Step 5's `train_and_evaluate()` returns the fitted engineered pipeline (test R² 0.979) and a report, but saves nothing.
Step 6 adds versioned saving and loading:
- pickle files in `models/`
- tamper-evident metadata (HMAC-signed JSON)
- a training-set reference profile (bins/shares for PSI in Step 15, plus fairness baselines)

`python -m northwind_loans.train` now also saves the model.

A read-only check showed:
- Raw predictions include 120 negatives and 61 above 5× income.
- Every real target is a multiple of 1000 and ≤ 5× income.

That is why `predicted_offer` needs the business rules below.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Business rules | `offer = floor(min(max(raw, 0), 5 × annual_income) / 1000) × 1000`. Missing or non-positive income → offer 0. New `business_rules.py`, reused later by predict/API. |
| Signing | Store the pickle's SHA-256 in the metadata; sign the metadata with HMAC-SHA256 using `MODEL_SIGNING_KEY` (.env). Stdlib only (`hashlib`, `hmac`). |
| On mismatch | `load_model` checks the signature, then the file SHA-256 **before** unpickling, and raises `ValueError`. A different sklearn version only logs a warning. |
| Bins home | New `reference_profile.py` with `make_bins` + `build_reference_profile`. |
| Metrics | `cv` (5-fold on the 80%), `train` (refit on 80%, in-sample), `test` (20%). |
| Profile values | Raw training values with NaN excluded, plus `missing_share`. dti comes from PolicyFeatures on the raw rows. |
| Listing | `registry.list_models()` + `python -m northwind_loans.registry` + `make models`. |

## New / changed files

### `config.py` (+ `.env.example`, `.env`)
- `MODEL_NAME = "loan_offer_model"`
- `MODEL_SIGNING_KEY = os.getenv("MODEL_SIGNING_KEY", "dev-only-insecure-key")`; the registry logs a warning when the default is used.

### `src/northwind_loans/business_rules.py`
- `apply_business_rules(raw_predictions, X) -> np.ndarray`: clip at 0, cap at `absolute_cap_income_multiple × income`, 0 if income is missing or ≤ 0, round down to `round_offer_to`.
- `count_rule_hits(raw_predictions, X) -> dict`: counts `clipped_to_zero`, `capped_at_income_multiple`, `zero_for_missing_income`.

### `src/northwind_loans/reference_profile.py`
- `make_bins(values, edges=None) -> (edges, shares)`:
  - Drops NaN.
  - With no `edges`: interior decile edges `np.quantile(v, [0.1 … 0.9])`, de-duplicated with `np.unique`.
  - Assigns values with `np.searchsorted(edges, v, side="left")`, giving bins `(-inf, e0], (e0, e1], …, (e_last, +inf)`; the outer bins are open-ended.
  - Shares = bincount / n.
  - Passing stored `edges` lets Step 15 reuse the same helper on live data.
- `numeric_summary(values)` → `{count, missing_share, mean, std, bin_edges, bin_shares}`.
- `category_shares(series)` → `{value: share}`.
- `fairness_baseline(X, y)`: mean of `max_loan_offered / annual_income` (income > 0) by gender and by age band (18-29, 30-39, 40-49, 50+), each with its row count.
- `build_reference_profile(X_train, y_train, pipeline)`:
  - numeric: annual_income, credit_score, monthly_existing_emi, requested_tenure_months, dti, predicted_offer
  - categorical: loan_purpose, employment_type
  - fairness
  - business_rule_counts

### `src/northwind_loans/registry.py`
The module docstring carries the **pickle warning**: loading executes code, so ONLY LOAD FILES YOU CREATED.

| Function | Purpose |
|---|---|
| `list_versions(model_dir)` | sorted ints from `loan_offer_model_v*.pkl` |
| `file_sha256(path)` | hash of a file |
| `sign_metadata(metadata)` | HMAC over canonical JSON (`sort_keys`, without `signature`) |
| `verify_metadata(metadata)` | `hmac.compare_digest` |
| `save_model(pipeline, metadata, model_dir=MODEL_DIR) -> dict` | details below |
| `load_model(version=None, model_dir=MODEL_DIR) -> (pipeline, metadata)` | details below |
| `list_models(model_dir)` | version, file, size_kb, created_at, test R²/RMSE |
| `main()` | prints the list (`make models`) |

`save_model`:
1. Takes the next version, `max + 1`.
2. Writes `models/loan_offer_model_v{N}.pkl` with `pickle.HIGHEST_PROTOCOL`.
3. Adds `model_name`, `version`, `created_at` (UTC ISO), `sklearn_version`, `python_version`, `pickle_protocol`, `model_file`, `model_sha256`, then `signature`.
4. Writes `loan_offer_model_v{N}.json`.
5. Returns `{model_name, version, model_path, metadata_path, model_sha256}`.

`load_model`:
1. Defaults to the highest version.
2. Verifies the signature and then the file SHA (raises on failure).
3. Warns if the installed sklearn version differs from the metadata.
4. Unpickles.

### `src/northwind_loans/train.py`
- Rename `test_metrics` → `score_metrics`. The report gains `train` (in-sample) and `reference_profile`, built from X_train and y_train.
- `build_metadata(report, pipeline) -> dict` covers:
  - train/test rows
  - raw input columns
  - model feature columns, plus the encoded names
  - `EXCLUDED_FEATURES` with reasons
  - metrics {cv, train, test}
  - a deep copy of `CREDIT_POLICY`
  - the reference profile
- `main()` gains `--model-dir` (default `MODEL_DIR`), calls `registry.save_model` and prints the version, path and size.
- `training_report.md` is unchanged except for the saved-model line.

### Other
- `Makefile`: new `models` target (+ `.PHONY`, help).
- Tests:
  - `test_business_rules.py`
  - `test_reference_profile.py`: zeros/duplicate edges, shares sum to 1, open-ended outer bins, reuse with given edges, age bands
  - `test_registry.py`:
    - v1 → v2 increments; latest is loaded by default; `load_model(1)` works
    - predictions identical after reload
    - edited JSON → raises; edited pkl → raises
    - re-signed metadata with another sklearn version → warning (caplog)
  - `test_train.py`: the CLI uses a tmp `--model-dir`, and the real `models/` stays unchanged
- `SECURITY.md`: pickle warning + signing key. Also README, CHANGELOG, `docs/plans/step-06-model-persistence.md`.

## Verification (show real output)
1. `make train`: prints the comparison table and "Saved loan_offer_model_v1".
2. `make models`: shows version, file, size and key metrics.
3. Script:
   - `load_model()`, then `assert np.array_equal(loaded.predict(X_test), in_memory.predict(X_test))`
   - print the metadata keys
   - print the reference profile summary for `annual_income` and `credit_score` (count, missing share, mean, std, edges, shares)
4. `pytest -q -W error`: all tests pass.
