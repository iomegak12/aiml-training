"""Tests for the cleaning module, using small hand-made frames."""

import math

import pandas as pd
import pytest

from northwind_loans import cleaning

COLUMNS = [
    "application_id", "application_date", "age", "gender", "marital_status", "dependents",
    "education", "city", "employment_type", "years_employed", "annual_income",
    "existing_loans_count", "monthly_existing_emi", "credit_score", "loan_purpose",
    "requested_amount", "requested_tenure_months", "has_collateral", "max_loan_offered",
]


def make_raw(rows: list[list[str]]) -> pd.DataFrame:
    """Build a raw-like frame (all strings) from row lists."""
    return pd.DataFrame(rows, columns=COLUMNS, dtype=str)


BASE = ["NWF-1", "2024-01-05", "30", "Male", "Single", "0", "Graduate", "Pune", "Salaried",
        "5", "600000", "0", "0", "750", "Home", "1000000", "120", "Yes", "900000"]


def variant(**changes: str) -> list[str]:
    """Copy BASE with some columns changed."""
    row = dict(zip(COLUMNS, BASE))
    row.update(changes)
    return [row[c] for c in COLUMNS]


@pytest.mark.parametrize(
    "value, expected",
    [
        ("9,26,000", 926_000.0),
        ("Rs. 757000", 757_000.0),
        ("10.14 L", 1_014_000.0),
        ("₹ 5,00,000", 500_000.0),
        ("INR 12000", 12_000.0),
        ("1500", 1_500.0),
        (1500, 1_500.0),
    ],
)
def test_parse_money(value: object, expected: float) -> None:
    assert cleaning.parse_money(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", ["", "abc", None, float("nan")])
def test_parse_money_returns_nan(value: object) -> None:
    assert math.isnan(cleaning.parse_money(value))


@pytest.mark.parametrize(
    "text",
    [
        "2024-01-05",   # YYYY-MM-DD
        "05/01/2024",   # DD/MM/YYYY -> 5 January (no day-first guessing)
        "05-Jan-2024",  # DD-Mon-YYYY
    ],
)
def test_parse_dates_three_formats(text: str) -> None:
    parsed, failures = cleaning.parse_dates(pd.Series([text]))
    assert failures == 0
    assert parsed.iloc[0] == pd.Timestamp("2024-01-05")


def test_parse_dates_counts_failures() -> None:
    parsed, failures = cleaning.parse_dates(pd.Series(["2024/01/05", None]))
    assert failures == 1 and parsed.isna().all()


@pytest.fixture
def cleaned() -> tuple[pd.DataFrame, dict]:
    rows = [
        BASE,
        BASE,  # exact duplicate
        variant(application_id=" nwf-1 ", annual_income="Rs. 800000"),  # same id, kept (last)
        variant(application_id="NWF-2", application_date="05/01/2024", gender=" male",
                education="UG", city="Bombay", employment_type="SE", loan_purpose="PL",
                has_collateral="0", annual_income="10.14 L"),
        variant(application_id="NWF-3", application_date="05-Jan-2024", age="999",
                annual_income="45000000", max_loan_offered="0"),
        variant(application_id="NWF-4", application_date="05-01-2024", age="20",
                years_employed="10", annual_income="0", credit_score="9999",
                max_loan_offered=""),
    ]
    return cleaning.clean_applications(make_raw(rows))


def test_duplicates_and_keep_last(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, report = cleaned
    assert report["rows_in"] == 6 and report["rows_out"] == 4
    assert report["duplicates_removed"] == {"exact": 1, "by_id": 1}
    assert df.application_id.is_unique
    assert df.loc[df.application_id == "NWF-1", "annual_income"].item() == 800_000


def test_categories_are_canonical(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, report = cleaned
    row = df[df.application_id == "NWF-2"].iloc[0]
    assert (row.gender, row.education, row.city) == ("Male", "Graduate", "Mumbai")
    assert (row.employment_type, row.loan_purpose) == ("Self-Employed", "Personal")
    assert row.has_collateral == False  # noqa: E712 - pandas boolean
    assert sum(report["unmapped_categories"].values()) == 0


def test_dates_all_formats(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, report = cleaned
    assert report["date_parse_failures"] == 0
    assert (df.application_date == pd.Timestamp("2024-01-05")).all()


def test_money_and_paise_fix(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, report = cleaned
    income = df.set_index("application_id").annual_income
    assert income["NWF-2"] == pytest.approx(1_014_000)
    assert income["NWF-3"] == 450_000  # 4.5 crore / 100
    assert report["incomes_parsed_from_text"] == 2
    assert report["incomes_divided_by_100"] == 1


def test_impossible_values_set_to_missing(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, report = cleaned
    rules = report["impossible_set_to_missing"]
    by_id = df.set_index("application_id")
    assert rules["annual_income <= 0"] == 1 and pd.isna(by_id.loc["NWF-4", "annual_income"])
    assert rules["age outside [18, 75]"] == 1 and pd.isna(by_id.loc["NWF-3", "age"])
    assert rules["credit_score outside [300, 900]"] == 1
    assert rules["years_employed > age - 14"] == 1
    assert pd.isna(by_id.loc["NWF-4", "years_employed"])


def test_target_not_dropped_or_imputed(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, report = cleaned
    by_id = df.set_index("application_id")
    assert by_id.loc["NWF-3", "max_loan_offered"] == 0
    assert pd.isna(by_id.loc["NWF-4", "max_loan_offered"])
    assert report["target_zero_count"] == 1


def test_dtypes(cleaned: tuple[pd.DataFrame, dict]) -> None:
    df, _ = cleaned
    assert str(df.age.dtype) == "Int64"
    assert str(df.requested_amount.dtype) == "float64"
    assert str(df.has_collateral.dtype) == "boolean"
    assert pd.api.types.is_datetime64_any_dtype(df.application_date)


def test_standardize_frame_without_id_and_target() -> None:
    raw = make_raw([variant(gender="F", annual_income="5.5 L")])
    raw = raw.drop(columns=["application_id", "max_loan_offered"])
    df, report = cleaning.standardize_frame(raw)
    assert df.loc[0, "gender"] == "Female"
    assert df.loc[0, "annual_income"] == pytest.approx(550_000)
    assert "max_loan_offered" not in df
