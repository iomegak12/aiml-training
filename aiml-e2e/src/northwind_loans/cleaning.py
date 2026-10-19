"""Clean raw loan applications into typed, standardised data.

Usage:
    python -m northwind_loans.cleaning [--input-dir DIR] [--output-dir DIR] [--report PATH]

Reads every data/raw/*.csv, writes data/processed/<name>.parquet and
reports/data_quality_report.json. Nothing is imputed and rows with a
missing target are kept.

At prediction time use `standardize_frame` - it works row by row and does
not need the target or application_id columns.
"""

import argparse
import json
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from northwind_loans.config import (
    INCOME_PAISE_THRESHOLD,
    LOG_LEVEL,
    PROCESSED_DATA,
    RAW_DATA,
    REPORTS_DIR,
    TARGET,
    VALID_RANGES,
)
from northwind_loans.profiling import ID_COLUMN, is_empty, read_raw_csv

logger = logging.getLogger(__name__)

DATE_COLUMN = "application_date"
MONEY_COLUMN = "annual_income"

INT_COLUMNS: list[str] = [
    "age",
    "dependents",
    "existing_loans_count",
    "credit_score",
    "requested_tenure_months",
]
FLOAT_COLUMNS: list[str] = [
    "years_employed",
    "monthly_existing_emi",
    "requested_amount",
    TARGET,
]

# Tried in this order - no day-first guessing.
DATE_FORMATS: list[str] = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y"]

LAKH = 100_000
_CURRENCY = re.compile(r"rs\.?|₹|inr", re.IGNORECASE)

# Keys are lower-case and stripped; values are the canonical categories.
CATEGORY_MAPS: dict[str, dict] = {
    "gender": {
        "male": "Male", "m": "Male",
        "female": "Female", "f": "Female",
        "other": "Other", "o": "Other",
    },
    "marital_status": {
        "single": "Single", "married": "Married",
        "divorced": "Divorced", "widowed": "Widowed",
    },
    "education": {
        "graduate": "Graduate", "ug": "Graduate", "bachelors": "Graduate",
        "postgraduate": "Postgraduate", "post graduate": "Postgraduate",
        "pg": "Postgraduate", "masters": "Postgraduate",
        "diploma": "Diploma",
        "higher secondary": "Higher Secondary", "hsc": "Higher Secondary",
        "12th": "Higher Secondary",
    },
    "employment_type": {
        "salaried": "Salaried",
        "self-employed": "Self-Employed", "self employed": "Self-Employed",
        "self_employed": "Self-Employed", "se": "Self-Employed",
        "business owner": "Business Owner", "business": "Business Owner",
        "proprietor": "Business Owner",
    },
    "loan_purpose": {
        "home": "Home", "home loan": "Home", "housing": "Home",
        "personal": "Personal", "pl": "Personal",
        "auto": "Auto", "car": "Auto", "vehicle": "Auto",
        "education": "Education", "student": "Education",
        "business": "Business", "sme": "Business",
    },
    "city": {
        **{name.lower(): name for name in [
            "Ahmedabad", "Bengaluru", "Bhopal", "Chandigarh", "Chennai",
            "Coimbatore", "Dehradun", "Delhi", "Gurugram", "Guwahati",
            "Hyderabad", "Indore", "Jaipur", "Kochi", "Kolkata", "Lucknow",
            "Mumbai", "Mysuru", "Nagpur", "Pune", "Raipur", "Vijayawada",
        ]},
        # old names -> modern names
        "bangalore": "Bengaluru", "bombay": "Mumbai", "gurgaon": "Gurugram",
        "madras": "Chennai", "calcutta": "Kolkata", "new delhi": "Delhi",
        "ncr": "Delhi", "mysore": "Mysuru",
    },
    "has_collateral": {
        "yes": True, "y": True, "true": True, "1": True,
        "no": False, "n": False, "false": False, "0": False,
    },
}


# --------------------------------------------------------------------------
# Small building blocks
# --------------------------------------------------------------------------
def parse_money(value: object) -> float:
    """Parse an INR amount like 'Rs. 7,57,000', '₹ 5,00,000' or '10.14 L'.

    A trailing 'L' means lakhs (x 100,000). Returns NaN if not parseable.
    """
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return np.nan
    if isinstance(value, (int, float)):
        return float(value)
    text = _CURRENCY.sub("", value).replace(",", "").replace(" ", "")
    if not text:
        return np.nan
    try:
        if text.lower().endswith("l"):
            return round(float(text[:-1]) * LAKH, 2)
        return float(text)
    except ValueError:
        return np.nan


def blank_to_nan(df: pd.DataFrame) -> pd.DataFrame:
    """Strip text values and turn empty strings into NaN."""
    df = df.copy()
    for column in df.select_dtypes(include="object").columns:
        stripped = df[column].map(lambda v: v.strip() if isinstance(v, str) else v)
        df[column] = stripped.mask(stripped == "")
    return df


def normalize_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Strip spaces and upper-case application_id (if present)."""
    df = df.copy()
    if ID_COLUMN in df:
        df[ID_COLUMN] = df[ID_COLUMN].str.strip().str.upper()
    return df


def drop_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Drop exact duplicate rows, then duplicate ids keeping the LAST one."""
    exact = int(df.duplicated().sum())
    df = df.drop_duplicates()
    by_id = int(df.duplicated(subset=[ID_COLUMN], keep="last").sum())
    df = df.drop_duplicates(subset=[ID_COLUMN], keep="last").reset_index(drop=True)
    return df, {"exact": exact, "by_id": by_id}


def parse_money_column(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Parse annual_income; return how many values were parsed from text."""
    df = df.copy()
    raw = df[MONEY_COLUMN]
    parsed = raw.map(parse_money).astype("float64")
    plain = pd.to_numeric(raw, errors="coerce")
    from_text = int((plain.isna() & parsed.notna()).sum())
    df[MONEY_COLUMN] = parsed
    return df, from_text


def convert_numbers(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Convert numeric columns (Int64 / float64); count values that failed."""
    df = df.copy()
    failures = {}
    for column in INT_COLUMNS + FLOAT_COLUMNS:
        if column not in df:
            continue
        converted = pd.to_numeric(df[column], errors="coerce")
        failures[column] = int((df[column].notna() & converted.isna()).sum())
        df[column] = converted.astype("Int64" if column in INT_COLUMNS else "float64")
    return df, failures


def parse_dates(series: pd.Series) -> tuple[pd.Series, int]:
    """Parse dates trying DATE_FORMATS in order; return (dates, failures)."""
    text = series.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    for fmt in DATE_FORMATS:
        todo = parsed.isna() & text.notna()
        parsed[todo] = pd.to_datetime(text[todo], format=fmt, errors="coerce")
    failures = int((parsed.isna() & text.notna()).sum())
    return parsed, failures


def _category_key(value: object) -> object:
    """Lower-case, stripped lookup key (NaN stays NaN)."""
    if not isinstance(value, str) and pd.isna(value):
        return value
    return str(value).strip().lower()


def map_categories(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Map every variant to its canonical value; unmapped values become NaN."""
    df = df.copy()
    unmapped = {}
    for column, mapping in CATEGORY_MAPS.items():
        if column not in df:
            continue
        mapped = df[column].map(_category_key).map(mapping)
        unmapped[column] = int((df[column].notna() & mapped.isna()).sum())
        df[column] = mapped.astype("boolean") if column == "has_collateral" else mapped
    return df, unmapped


def fix_paise_incomes(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Incomes above the threshold were entered 100x too large - divide by 100."""
    df = df.copy()
    too_large = df[MONEY_COLUMN] > INCOME_PAISE_THRESHOLD
    df.loc[too_large, MONEY_COLUMN] = df.loc[too_large, MONEY_COLUMN] / 100
    return df, int(too_large.sum())


def _set_missing(df: pd.DataFrame, column: str, mask: pd.Series) -> int:
    """Set df[column] to missing where mask is True (in place); return count."""
    mask = mask.fillna(False).astype(bool)
    df.loc[mask, column] = np.nan
    return int(mask.sum())


def set_impossible_to_missing(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Blank out impossible values, counted per rule. Rows are never dropped."""
    df = df.copy()
    counts = {}
    if MONEY_COLUMN in df:
        counts["annual_income <= 0"] = _set_missing(df, MONEY_COLUMN, df[MONEY_COLUMN] <= 0)
    for column, (low, high) in VALID_RANGES.items():
        if column in df:
            outside = (df[column] < low) | (df[column] > high)
            counts[f"{column} outside [{low}, {high}]"] = _set_missing(df, column, outside)
    if "years_employed" in df:
        years = df["years_employed"]
        counts["years_employed < 0"] = _set_missing(df, "years_employed", years < 0)
        if "age" in df:
            too_long = df["years_employed"] > df["age"] - 14
            counts["years_employed > age - 14"] = _set_missing(df, "years_employed", too_long)
    return df, counts


# --------------------------------------------------------------------------
# Main entry points
# --------------------------------------------------------------------------
def standardize_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Apply all row-wise cleaning rules (safe to use at prediction time).

    Columns that are not present (e.g. target, application_id) are skipped.
    """
    df = normalize_ids(blank_to_nan(df))
    report: dict = {"incomes_parsed_from_text": 0}
    if MONEY_COLUMN in df:
        df, report["incomes_parsed_from_text"] = parse_money_column(df)
    df, report["numeric_parse_failures"] = convert_numbers(df)
    report["date_parse_failures"] = 0
    if DATE_COLUMN in df:
        df[DATE_COLUMN], report["date_parse_failures"] = parse_dates(df[DATE_COLUMN])
    df, report["unmapped_categories"] = map_categories(df)
    report["incomes_divided_by_100"] = 0
    if MONEY_COLUMN in df:
        df, report["incomes_divided_by_100"] = fix_paise_incomes(df)
    df, report["impossible_set_to_missing"] = set_impossible_to_missing(df)
    return df, report


def clean_applications(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Full training-time cleaning: ids, de-duplication, then standardize_frame."""
    rows_in = len(df)
    df = normalize_ids(df)
    df, duplicates_removed = drop_duplicates(df)
    df, standard_report = standardize_frame(df)
    report = {
        "rows_in": rows_in,
        "rows_out": len(df),
        "duplicates_removed": duplicates_removed,
        **standard_report,
        "target_zero_count": int((df[TARGET] == 0).sum()) if TARGET in df else 0,
        "missing_after": {col: int(n) for col, n in df.isna().sum().items()},
    }
    logger.info("Cleaned %s -> %s rows", rows_in, len(df))
    return df, report


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def print_summary(name: str, raw: pd.DataFrame, report: dict) -> None:
    """Print a before/after table for one file."""
    print(f"\n=== {name} ===")
    print(f"{'':26}{'before':>10}{'after':>10}")
    print(f"{'rows':26}{report['rows_in']:>10,}{report['rows_out']:>10,}")
    print("missing values:")
    for column, after in report["missing_after"].items():
        before = int(is_empty(raw[column]).sum())
        print(f"  {column:24}{before:>10,}{after:>10,}")
    dups = report["duplicates_removed"]
    print(f"duplicates removed      : exact {dups['exact']:,}, by id {dups['by_id']:,}")
    print(f"incomes parsed from text: {report['incomes_parsed_from_text']:,}")
    print(f"incomes divided by 100  : {report['incomes_divided_by_100']:,}")
    print(f"date parse failures     : {report['date_parse_failures']:,}")
    print(f"unmapped categories     : {sum(report['unmapped_categories'].values()):,}")
    print("impossible -> missing   :")
    for rule, count in report["impossible_set_to_missing"].items():
        print(f"  {rule:42}{count:>6,}")


def main(argv: list[str] | None = None) -> None:
    """Clean every raw CSV and write parquet files plus a quality report."""
    parser = argparse.ArgumentParser(description="Clean raw loan application CSVs.")
    parser.add_argument("--input-dir", type=Path, default=RAW_DATA.parent)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DATA)
    parser.add_argument("--report", type=Path, default=REPORTS_DIR / "data_quality_report.json")
    args = parser.parse_args(argv)

    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = {}
    for csv_path in sorted(args.input_dir.glob("*.csv")):
        raw = read_raw_csv(csv_path)
        clean, report = clean_applications(raw)
        out_path = args.output_dir / f"{csv_path.stem}.parquet"
        clean.to_parquet(out_path, index=False)
        logger.info("Wrote %s", out_path)
        reports[csv_path.name] = report
        print_summary(csv_path.name, raw, report)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(f"\nQuality report: {args.report}")


if __name__ == "__main__":
    main()
