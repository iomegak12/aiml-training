# Step 3 — Data Engineering (cleaning)

## Context
Step 2's profile showed messy raw data:
- 700 exact duplicate rows and 1,000 duplicate IDs
- incomes written as text (`Rs. 757000`, `10.14 L`, `9,26,000`)
- 3 date formats
- case and spelling variants in the categories
- paise-scaled incomes and out-of-range values

Step 3 turns `data/raw/*.csv` into typed `data/processed/*.parquet` plus a quality report.
The code must be reusable at prediction time.
Nothing is imputed, and rows with a missing target are **not** dropped.

## Decisions (agreed with Ram)
- **Dates:** try `%Y-%m-%d`, `%d/%m/%Y`, `%d-%m-%Y`, `%d-%b-%Y` in that order, with no dayfirst guessing. Failures become NaT and are counted.
- **Category lookup:** `strip().lower()` the value, then use a dict of lowercase variants → canonical value.
- **Unmapped values:** a non-empty value that doesn't map becomes NaN and is counted per column (expected 0).
- **Target:** `max_loan_offered == 0` (80 rows) is left as is; only its count goes in the report.
- **Years rule:** `years_employed > age - 14` blanks only `years_employed`. It runs after the age range check.
- **VALID_RANGES:** values outside the inclusive bounds become NaN, counted per rule.
- **Output:** each `data/raw/<name>.csv` becomes `data/processed/<name>.parquet`. One `reports/data_quality_report.json` holds a report per file name.
- **Paise rule:** income **>** `INCOME_PAISE_THRESHOLD` (the word "above") is divided by 100. No raw value equals 2 crore exactly.

## File: `src/northwind_loans/cleaning.py`
Reuses `profiling.read_raw_csv` (same no-auto-convert read) and `profiling.is_empty`.

Constants:
- `INT_COLUMNS` → `Int64`: age, dependents, existing_loans_count, credit_score, requested_tenure_months.
- `FLOAT_COLUMNS` → float64: years_employed, monthly_existing_emi, requested_amount, max_loan_offered. `annual_income` goes through `parse_money` instead.
- `DATE_FORMATS`.
- `CATEGORY_MAPS` (lowercase key → canonical):
  - gender: m/male → Male, f/female → Female, o/other → Other
  - marital_status: the 4 values
  - education:
    - ug/bachelors/graduate → Graduate
    - pg/masters/post graduate/postgraduate → Postgraduate
    - diploma → Diploma
    - 12th/hsc/higher secondary → Higher Secondary
  - employment_type:
    - salaried → Salaried
    - se/self employed/self_employed/self-employed → Self-Employed
    - business/proprietor/business owner → Business Owner
  - loan_purpose:
    - home loan/housing → Home
    - pl → Personal
    - car/vehicle → Auto
    - student → Education
    - sme → Business
  - city: the 22 modern names, plus bangalore, bombay, gurgaon, madras, calcutta, new delhi, ncr and mysore aliases
  - has_collateral: yes/y/true/1 → True, no/n/false/0 → False (`boolean` dtype)

Functions (small, type-hinted, docstrings, `logger`):

| Function | Purpose |
|---|---|
| `parse_money(value) -> float` | NaN/empty → NaN. Remove `rs.`, `rs`, `₹`, `inr` (any case), spaces and commas. A trailing `l`/`L` means × 100,000. Unparseable → NaN. Numbers pass through. |
| `normalize_ids(df)` | `application_id` strip + upper |
| `drop_duplicates(df) -> (df, report)` | drops exact duplicate rows, then duplicate IDs `keep="last"` |
| `parse_dates(series) -> (series, failures)` | tries the formats in order |
| `map_categories(df) -> (df, unmapped)` | applies `CATEGORY_MAPS` |
| `fix_paise_incomes(df) -> (df, count)` | divides scaled incomes by 100 |
| `set_impossible_to_missing(df) -> (df, counts)` | rules below, in order |
| `standardize_frame(df) -> (df, report)` | row-wise only, safe for one API request: blanks → NaN, IDs, money, numbers, dates, categories, paise fix, impossible values. Skips columns that aren't present (e.g. target or ID at predict time). |
| `clean_applications(df) -> (df, report)` | normalise IDs → `drop_duplicates` → `standardize_frame` → missing-after counts |
| `main(argv=None)` | CLI (below) |

`set_impossible_to_missing` rules, in order:
1. `annual_income <= 0`
2. each `VALID_RANGES` column outside its bounds
3. `years_employed < 0`
4. `years_employed > age - 14`

Report keys (per file):
- `rows_in`, `rows_out`
- `duplicates_removed` {exact, by_id}
- `incomes_parsed_from_text`, `incomes_divided_by_100`
- `impossible_set_to_missing` {rule: n}
- `numeric_parse_failures` {col: n}
- `unmapped_categories` {col: n}
- `date_parse_failures`
- `target_zero_count`
- `missing_after` {col: n}

CLI: `python -m northwind_loans.cleaning [--input-dir data/raw] [--output-dir data/processed] [--report reports/data_quality_report.json]`.
- Sets up logging with `LOG_LEVEL`.
- For each CSV: read, clean, write parquet (`index=False`).
- Prints a before/after table: rows plus missing values per column.

## Other edits
- `Makefile`: the `clean-data` target runs `$(PY) -m northwind_loans.cleaning`.
- `tests/test_cleaning.py`:
  - `parse_money` cases: `9,26,000`, `Rs. 757000`, `10.14 L`, `₹ 5,00,000`, `INR 12000`, `""`, `abc`, `1500`.
  - Run `clean_applications` on a small frame and check: dedup counts, keep-last, canonical categories, both date styles, paise fix, each impossible rule, zero target kept, missing-target row kept.
  - `standardize_frame` works without `application_id` and target.
- `CHANGELOG.md` and `README.md` updated. No changes to `data/raw` or `data/sample`.

## Verification (show real output)
1. `make clean-data`: shows the before/after summary table.
2. Acceptance script on the parquet file:
   - `assert clean_df.application_id.is_unique`
   - sorted unique values of every categorical column
   - `parse_money` examples
   - min/max `application_date`
   - dtypes
3. `make test`: all tests pass, old and new.
4. `git status --short data/raw data/sample`: unchanged.
