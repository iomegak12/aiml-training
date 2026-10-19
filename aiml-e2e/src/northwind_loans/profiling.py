"""Profile the raw loan applications CSV - measure problems, clean nothing.

Usage:
    python -m northwind_loans.profiling [--input PATH] [--output-dir DIR]

Writes `data_profile.json` and `data_profile.md` to the reports folder.
"""

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from northwind_loans.config import (
    INCOME_PAISE_THRESHOLD,
    LOG_LEVEL,
    RANDOM_STATE,
    RAW_DATA,
    REPORTS_DIR,
    VALID_RANGES,
)

logger = logging.getLogger(__name__)

ID_COLUMN = "application_id"
DATE_COLUMN = "application_date"

TEXT_COLUMNS: list[str] = [
    "gender",
    "marital_status",
    "education",
    "city",
    "employment_type",
    "loan_purpose",
    "has_collateral",
]

NUMERIC_COLUMNS: list[str] = [
    "age",
    "dependents",
    "years_employed",
    "annual_income",
    "existing_loans_count",
    "monthly_existing_emi",
    "credit_score",
    "requested_amount",
    "requested_tenure_months",
    "max_loan_offered",
]

DATE_PATTERNS: dict[str, str] = {
    "YYYY-MM-DD": r"^\d{4}-\d{2}-\d{2}$",
    "DD/MM/YYYY": r"^\d{2}/\d{2}/\d{4}$",
    "DD-Mon-YYYY": r"^\d{2}-[A-Za-z]{3}-\d{4}$",
}

TOP_N = 15
N_SAMPLES = 5


# --------------------------------------------------------------------------
# Reading and parsing helpers
# --------------------------------------------------------------------------
def read_raw_csv(path: Path) -> pd.DataFrame:
    """Read the CSV with every value as a string - nothing is auto-converted."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])
    logger.info("Read %s rows x %s columns from %s", len(df), df.shape[1], path)
    return df


def is_empty(series: pd.Series) -> pd.Series:
    """True where a value is empty after stripping spaces."""
    return series.str.strip() == ""


def to_number(series: pd.Series) -> pd.Series:
    """Parse strings like '9,26,000' to floats (NaN if not parseable).

    Used only for counting in the profile; the data itself is not changed.
    """
    cleaned = series.str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(cleaned, errors="coerce")


# --------------------------------------------------------------------------
# Profile sections
# --------------------------------------------------------------------------
def missing_values(df: pd.DataFrame) -> dict[str, dict]:
    """Missing (empty) values per column: count and percentage."""
    result = {}
    for column in df.columns:
        count = int(is_empty(df[column]).sum())
        result[column] = {"count": count, "pct": round(100 * count / len(df), 2)}
    return result


def duplicates(df: pd.DataFrame) -> dict[str, dict]:
    """Exact duplicate rows and duplicate application ids (stripped, upper-cased).

    extra_rows = rows beyond the first occurrence (what de-duplication removes)
    affected   = distinct rows / ids that occur more than once
    """
    row_counts = df.value_counts()
    ids = df[ID_COLUMN].str.strip().str.upper()
    id_counts = ids.value_counts()
    return {
        "exact_rows": {
            "extra_rows": int(df.duplicated().sum()),
            "affected": int((row_counts > 1).sum()),
        },
        "application_id": {
            "extra_rows": int(ids.duplicated().sum()),
            "affected": int((id_counts > 1).sum()),
        },
    }


def text_column_profile(df: pd.DataFrame) -> dict[str, dict]:
    """Distinct count and top values (raw, so case/space variants show up)."""
    result = {}
    for column in TEXT_COLUMNS:
        counts = df[column].value_counts()
        result[column] = {
            "distinct": int(counts.size),
            f"top_{TOP_N}": {value: int(n) for value, n in counts.head(TOP_N).items()},
        }
    return result


def numeric_column_profile(df: pd.DataFrame) -> dict[str, dict]:
    """Non-empty count, random samples, unparseable values and min/max."""
    result = {}
    for column in NUMERIC_COLUMNS:
        non_empty = df.loc[~is_empty(df[column]), column]
        parsed = to_number(non_empty)
        unparseable = non_empty[parsed.isna()]
        samples = non_empty.sample(min(N_SAMPLES, len(non_empty)), random_state=RANDOM_STATE)
        result[column] = {
            "non_empty": int(non_empty.size),
            "samples": samples.tolist(),
            "unparseable": int(unparseable.size),
            "unparseable_examples": unparseable.unique()[:N_SAMPLES].tolist(),
            "min": None if parsed.isna().all() else float(parsed.min()),
            "max": None if parsed.isna().all() else float(parsed.max()),
        }
    return result


def date_format_counts(series: pd.Series) -> dict[str, int]:
    """Count values per date format; anything not matching is 'other'."""
    matched = pd.Series(False, index=series.index)
    result = {}
    for name, pattern in DATE_PATTERNS.items():
        hits = series.str.strip().str.match(pattern)
        result[name] = int(hits.sum())
        matched |= hits
    result["other"] = int((~matched).sum())
    return result


def out_of_range_counts(df: pd.DataFrame) -> dict[str, int]:
    """Count values that break the valid ranges and sanity rules from config."""
    result = {}
    for column, (low, high) in VALID_RANGES.items():
        values = to_number(df[column])
        result[f"{column} outside [{low}, {high}]"] = int(((values < low) | (values > high)).sum())

    income = to_number(df["annual_income"])
    result["annual_income <= 0"] = int((income <= 0).sum())
    result[f"annual_income >= {INCOME_PAISE_THRESHOLD}"] = int(
        (income >= INCOME_PAISE_THRESHOLD).sum()
    )

    years = to_number(df["years_employed"])
    age = to_number(df["age"])
    result["years_employed > age - 14"] = int((years > age - 14).sum())
    return result


def profile_raw(path: Path) -> dict:
    """Build the full raw-data profile as a JSON-friendly dictionary."""
    df = read_raw_csv(path)
    profile = {
        "source": str(path),
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "column_names": df.columns.tolist(),
        "missing": missing_values(df),
        "duplicates": duplicates(df),
        "text_columns": text_column_profile(df),
        "numeric_columns": numeric_column_profile(df),
        "application_date_formats": date_format_counts(df[DATE_COLUMN]),
        "out_of_range": out_of_range_counts(df),
    }
    logger.info("Profile built for %s", path)
    return profile


# --------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------
def write_json(profile: dict, path: Path) -> None:
    """Write the profile as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote %s", path)


def _md_table(headers: list[str], rows: list[list]) -> str:
    """Render a simple Markdown table."""
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def _show(value: str) -> str:
    """Show a raw value with quotes so leading/trailing spaces are visible."""
    return f"`{value!r}`"


def write_markdown(profile: dict, path: Path) -> None:
    """Write the profile as readable Markdown tables."""
    parts = [
        "# Raw Data Profile",
        f"Source: `{profile['source']}`",
        "## a. Shape",
        _md_table(["Rows", "Columns"], [[profile["rows"], profile["columns"]]]),
        "## b. Missing values (empty after strip)",
        _md_table(
            ["Column", "Missing", "%"],
            [[col, m["count"], m["pct"]] for col, m in profile["missing"].items()],
        ),
        "## c. Duplicates",
        _md_table(
            ["Check", "Extra rows", "Affected"],
            [[name, d["extra_rows"], d["affected"]] for name, d in profile["duplicates"].items()],
        ),
        "## d. Text columns",
        _md_table(
            ["Column", "Distinct"],
            [[col, t["distinct"]] for col, t in profile["text_columns"].items()],
        ),
    ]
    for column, info in profile["text_columns"].items():
        top = info[f"top_{TOP_N}"]
        parts.append(f"### {column} - top {TOP_N}")
        parts.append(_md_table(["Value", "Count"], [[_show(v), n] for v, n in top.items()]))

    parts += [
        "## e. Numeric-looking columns",
        _md_table(
            ["Column", "Non-empty", "Unparseable", "Min", "Max", "Samples", "Unparseable examples"],
            [
                [
                    col,
                    n["non_empty"],
                    n["unparseable"],
                    n["min"],
                    n["max"],
                    ", ".join(_show(s) for s in n["samples"]),
                    ", ".join(_show(s) for s in n["unparseable_examples"]),
                ]
                for col, n in profile["numeric_columns"].items()
            ],
        ),
        "## f. application_date formats",
        _md_table(["Format", "Count"], list(map(list, profile["application_date_formats"].items()))),
        "## g. Out-of-range checks",
        _md_table(["Rule", "Count"], list(map(list, profile["out_of_range"].items()))),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    logger.info("Wrote %s", path)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def print_summary(profile: dict, json_path: Path, md_path: Path) -> None:
    """Print a short human-readable summary."""
    total_missing = sum(m["count"] for m in profile["missing"].values())
    dups = profile["duplicates"]
    print(f"Profiled {profile['rows']:,} rows x {profile['columns']} columns")
    print(f"Missing cells        : {total_missing:,}")
    print(f"Duplicate rows       : {dups['exact_rows']['extra_rows']:,} extra")
    print(f"Duplicate app ids    : {dups['application_id']['extra_rows']:,} extra")
    print(f"Date formats         : {profile['application_date_formats']}")
    print("Out of range:")
    for rule, count in profile["out_of_range"].items():
        print(f"  {rule:42} {count:>6,}")
    print(f"Reports: {json_path}\n         {md_path}")


def main(argv: list[str] | None = None) -> None:
    """Profile the raw CSV and write JSON + Markdown reports."""
    parser = argparse.ArgumentParser(description="Profile the raw loan applications CSV.")
    parser.add_argument("--input", type=Path, default=RAW_DATA, help="CSV to profile")
    parser.add_argument("--output-dir", type=Path, default=REPORTS_DIR, help="report folder")
    args = parser.parse_args(argv)

    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    profile = profile_raw(args.input)
    json_path = args.output_dir / "data_profile.json"
    md_path = args.output_dir / "data_profile.md"
    write_json(profile, json_path)
    write_markdown(profile, md_path)
    print_summary(profile, json_path, md_path)


if __name__ == "__main__":
    main()
