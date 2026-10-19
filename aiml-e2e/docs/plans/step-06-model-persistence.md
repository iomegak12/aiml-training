# Step 6 — Model Persistence with Signed Metadata (plan & outcome)

## Context
Step 5's `train_and_evaluate()` returned the fitted engineered pipeline but saved nothing.
Step 6 adds:
- versioned pickles in `models/`
- tamper-evident, HMAC-signed metadata
- a training-set reference profile (decile bins for PSI in Step 15, plus a fairness baseline)

`python -m northwind_loans.train` now also saves the model.

## Decisions (agreed with Ram)
| Topic | Decision |
|---|---|
| Business rules | `offer = floor(min(max(raw, 0), 5 × income) / 1000) × 1000`; missing or ≤ 0 income → 0. Data check: all targets are multiples of 1000 and ≤ 5× income; raw predictions had 120 negatives and 61 above 5× income. |
| Signing | SHA-256 of the pickle stored in the metadata; metadata signed with HMAC-SHA256 using `MODEL_SIGNING_KEY` (.env). Stdlib only. |
| On mismatch | Signature, then file hash, verified **before** unpickling → `ValueError`. sklearn version difference → warning only. |
| Bins home | `reference_profile.py` (`make_bins`, reused by Step 15) |
| Metrics | `cv` (5-fold on 80%), `train` (in-sample), `test` (20%) |
| Profile values | Raw training values, NaN excluded, plus `missing_share`; dti via PolicyFeatures |
| Listing | `registry.list_models()`, `python -m northwind_loans.registry`, `make models` |

## Modules
- **`business_rules.py`**: `apply_business_rules(raw, X)`, `count_rule_hits(raw, X)`.
- **`reference_profile.py`**:
  - `make_bins(values, edges=None)`: interior decile edges, de-duplicated with `np.unique`; values assigned with `np.searchsorted(side="left")`. Bins are `(-inf, e0] … (e_last, +inf)`. Pass `edges` to bin live data.
  - `numeric_summary`, `category_shares`, `age_band`, `fairness_baseline`, `build_reference_profile`.
- **`registry.py`** (module docstring carries the pickle warning):
  - versions and paths: `list_versions`, `model_path`, `metadata_path`
  - signing: `file_sha256`, `sign_metadata`, `verify_metadata`
  - `save_model(pipeline, metadata, model_dir) -> {model_name, version, model_path, metadata_path, model_sha256}`
  - `load_model(version=None, model_dir) -> (pipeline, metadata)`
  - `list_models`, `main`
- **`train.py`**: `score_metrics` (renamed from `test_metrics`), `build_metadata(report, pipeline)`, and `main --model-dir` saves the model.
- **`config.py`**: `MODEL_NAME`, `DEFAULT_SIGNING_KEY`, `MODEL_SIGNING_KEY`. A random key goes in `.env`; a placeholder goes in `.env.example`.

## Metadata keys (`models/loan_offer_model_vN.json`)
- **Registry:** `model_name`, `version`, `created_at`, `sklearn_version`, `python_version`, `pickle_protocol`, `model_file`, `model_sha256`
- **Data:** `target`, `train_rows`, `test_rows`
- **Columns:** `raw_input_columns`, `model_feature_columns`, `encoded_feature_names`, `excluded_features` (with reasons)
- **Training:** `metrics` {cv, train, test}, `training_settings`, `credit_policy`
- **Reference profile:**
  - `reference_profile` {numeric, categorical, fairness, business_rule_counts}
  - numeric columns: annual_income, credit_score, monthly_existing_emi, requested_tenure_months, dti, predicted_offer
  - categorical columns: loan_purpose, employment_type
- **Signature:** `signature`, HMAC over the rest; the metadata is JSON round-tripped before signing.

## Tests (14 new; full suite 67 passed with `-W error`)
- `test_business_rules.py`: clip, round down, cap, missing/zero income, and rule counts.
- `test_reference_profile.py`:
  - even deciles
  - many zeros → unique edges, 70% in the first bin
  - NaN ignored
  - reused edges with open-ended outer bins
  - age bands and fairness means
- `test_registry.py`:
  - v1 → v2; latest loaded by default; `load_model(1)`
  - identical predictions after reload
  - metadata fields and listing
  - edited JSON refused; edited pickle refused
  - re-signed sklearn mismatch → warning
  - no models → `FileNotFoundError`
- `test_train.py`: metadata contents; the CLI saves into a tmp `--model-dir` and leaves the real `models/` untouched.

## Outcome (2026-10-15)
- `make train` saved **v1** (4.5 KB). The acceptance script saved **v2** and reloaded the latest: `np.array_equal` on all 10,956 test predictions → **True**.
- `make models`: v1 and v2, both test R² 0.9785, signature OK.
- Metrics: train R² 0.9786 vs test R² 0.9785, so no overfitting.
- Business-rule hits on the training set: 120 clipped to 0, 61 capped at 5× income, 373 → 0 for missing income.
- Reference profile:

  | Column | Count | Missing | Mean | Bins |
  |---|---|---|---|---|
  | annual_income | 43,451 | 0.85% | ₹11.4 L | 10 even bins, edges ₹4.57 L … ₹19.9 L |
  | credit_score | 42,258 | 3.57% | 730.6 (std 60.3) | 10 bins, edges 653 … 808 |

- Fairness baseline (offer / income): Female 1.753, Male 1.758, Other 1.861; age bands between 1.744 and 1.770.

## Not in this step
Prediction CLI, API, drift/PSI computation, model promotion and retention policy.
