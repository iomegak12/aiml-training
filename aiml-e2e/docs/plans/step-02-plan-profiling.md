# Step 2 — Profile the raw data (no cleaning)

## Context
Before cleaning, we measure what is wrong with `data/raw/loan_applications_raw.csv`
(56,000 rows × 19 cols). Findings from a read-only peek:
- Missing values are empty strings only.
- Text values are messy (`' Male'`, `'MALE'`, `'M'`; `Y`/`TRUE`/`1`).
- `annual_income` has Indian commas (`9,26,000`).
- There are 3 date formats.
- 700 exact duplicate rows; 1,000 duplicate IDs.

Output: a dict + JSON + Markdown report. Nothing is modified or saved as clean data.

## Decisions (agreed with Ram)
- Read with `dtype=str, keep_default_na=False, na_values=[]`. Nothing is auto-converted.
- "Missing" = value is empty after `strip()`. Report count and % (2 dp).
- Duplicates: report both `extra_rows` (`duplicated().sum()`) and `affected` (distinct values seen more than once):
  - exact rows
  - `application_id` after `strip().upper()`
- Numeric parse is **for counting only**: strip commas and spaces, then `pd.to_numeric(errors="coerce")`.
- Numeric columns report:
  - non-empty count
  - 5 samples via `sample(5, random_state=RANDOM_STATE)`
  - unparseable count + up to 5 examples
  - parsed min/max
- Text columns report distinct count and top 15 with counts on the **raw** values, so case and space variants show up. Markdown shows values in backticks so leading/trailing spaces are visible.

## File: `src/northwind_loans/profiling.py`
Constants: `ID_COLUMN`, `DATE_COLUMN`, `TEXT_COLUMNS` (7), `NUMERIC_COLUMNS` (10), and `DATE_PATTERNS`:
- `YYYY-MM-DD`: `^\d{4}-\d{2}-\d{2}$`
- `DD/MM/YYYY`: `^\d{2}/\d{2}/\d{4}$`
- `DD-Mon-YYYY`: `^\d{2}-[A-Za-z]{3}-\d{4}$`
- anything else counts as `other`

Small functions (type hints and docstrings, `logger = logging.getLogger(__name__)`):

| Function | Returns |
|---|---|
| `read_raw_csv(path)` | DataFrame of strings |
| `to_number(series)` | float Series (commas removed, coerced); used for counting only |
| `missing_values(df)` | `{col: {"count", "pct"}}` |
| `duplicates(df)` | exact rows + normalised IDs (extra_rows, affected) |
| `text_column_profile(df)` | `{col: {"distinct", "top_15": {value: count}}}` |
| `numeric_column_profile(df)` | `{col: {"non_empty", "samples", "unparseable", "unparseable_examples", "min", "max"}}` |
| `date_format_counts(series)` | `{"YYYY-MM-DD", "DD/MM/YYYY", "DD-Mon-YYYY", "other"}` counts |
| `out_of_range_counts(df)` | one count per rule (below) |
| `profile_raw(path)` | `{"source", "rows", "columns", "column_names", "missing", "duplicates", "text_columns", "numeric_columns", "application_date_formats", "out_of_range"}` |
| `write_json(profile, path)` | writes the JSON file |
| `write_markdown(profile, path)` | writes Markdown tables (one section per item a–g) |
| `main(argv=None)` | CLI |

`out_of_range_counts` rules:
- each `VALID_RANGES` column: count of values `< lo` or `> hi`
- `annual_income <= 0`
- `annual_income >= INCOME_PAISE_THRESHOLD`
- `years_employed > age - 14`, only where both values parse

CLI: `python -m northwind_loans.profiling [--input PATH] [--output-dir DIR]`, defaulting to `RAW_DATA` / `REPORTS_DIR`.
- Sets up `logging.basicConfig(level=LOG_LEVEL)`.
- Writes `reports/data_profile.json` and `reports/data_profile.md`.
- Prints a short summary: rows/cols, total missing cells, duplicates, date-format counts, out-of-range counts.

## Other edits
- `Makefile`: the `profile` target runs `$(PY) -m northwind_loans.profiling`.
- `tests/test_profiling.py`: a 4–5 row CSV in `tmp_path` with known issues. Assert:
  - missing counts
  - duplicate counts
  - date-format counts
  - out-of-range counts
  - that a comma income parses
  - that the CLI writes both files
- `CHANGELOG.md` (Unreleased) and `README.md`: list `profile` as available.
- No changes to `data/`.

## Verification (show real output)
1. `make profile`: shows the printed summary.
2. Read `reports/data_profile.json` back in Python and print:
   - the missing-value table (col, count, %)
   - distinct counts for the 7 text columns
3. `make test`: all tests pass, old and new.
4. `git status --short data/`: unchanged.
