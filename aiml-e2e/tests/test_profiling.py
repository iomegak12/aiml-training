"""Tests for the raw-data profiler, using a tiny hand-made CSV."""

import json
from pathlib import Path

import pytest

from northwind_loans import profiling

HEADER = (
    "application_id,application_date,age,gender,marital_status,dependents,education,city,"
    "employment_type,years_employed,annual_income,existing_loans_count,monthly_existing_emi,"
    "credit_score,loan_purpose,requested_amount,requested_tenure_months,has_collateral,"
    "max_loan_offered"
)
ROWS = [
    # normal row, ISO date
    'NWF-1,2024-01-05,30,Male,Single,0,Graduate,Pune,Salaried,5,600000,0,0,750,Home,1000000,120,Yes,900000',
    # exact duplicate of row 1
    'NWF-1,2024-01-05,30,Male,Single,0,Graduate,Pune,Salaried,5,600000,0,0,750,Home,1000000,120,Yes,900000',
    # same id with spaces/lowercase, DD/MM/YYYY, comma income, missing credit score
    ' nwf-1 ,05/01/2024,40, male,,2,UG,Delhi,SALARIED,10,"9,26,000",1,5000,,Personal,500000,36,Y,400000',
    # DD-Mon-YYYY, age out of range, years_employed > age - 14, zero income
    'NWF-2,05-Jan-2024,16,F,Married,1,Graduate,Pune,Salaried,8,0,0,0,950,Auto,300000,12,N,',
    # unknown date format, income above paise threshold
    'NWF-3,2024/01/05,45,Female,Married,11,PG,,Business,20,25000000,2,9000,700,Business,900000,400,No,800000',
]


@pytest.fixture
def raw_csv(tmp_path: Path) -> Path:
    path = tmp_path / "raw.csv"
    path.write_text("\n".join([HEADER, *ROWS]) + "\n", encoding="utf-8")
    return path


def test_shape_and_missing(raw_csv: Path) -> None:
    profile = profiling.profile_raw(raw_csv)
    assert profile["rows"] == 5
    assert profile["columns"] == 19
    assert profile["missing"]["credit_score"] == {"count": 1, "pct": 20.0}
    assert profile["missing"]["city"]["count"] == 1
    assert profile["missing"]["max_loan_offered"]["count"] == 1


def test_duplicates(raw_csv: Path) -> None:
    dups = profiling.profile_raw(raw_csv)["duplicates"]
    assert dups["exact_rows"] == {"extra_rows": 1, "affected": 1}
    assert dups["application_id"] == {"extra_rows": 2, "affected": 1}


def test_text_values_are_raw(raw_csv: Path) -> None:
    gender = profiling.profile_raw(raw_csv)["text_columns"]["gender"]
    assert gender["distinct"] == 4  # Male, ' male', F, Female
    assert gender["top_15"]["Male"] == 2


def test_numeric_columns_parse_commas(raw_csv: Path) -> None:
    income = profiling.profile_raw(raw_csv)["numeric_columns"]["annual_income"]
    assert income["non_empty"] == 5
    assert income["unparseable"] == 0
    assert income["max"] == 25_000_000
    assert len(income["samples"]) == 5


def test_date_formats(raw_csv: Path) -> None:
    formats = profiling.profile_raw(raw_csv)["application_date_formats"]
    assert formats == {"YYYY-MM-DD": 2, "DD/MM/YYYY": 1, "DD-Mon-YYYY": 1, "other": 1}


def test_out_of_range(raw_csv: Path) -> None:
    oor = profiling.profile_raw(raw_csv)["out_of_range"]
    assert oor["age outside [18, 75]"] == 1
    assert oor["credit_score outside [300, 900]"] == 1
    assert oor["requested_tenure_months outside [6, 360]"] == 1
    assert oor["dependents outside [0, 10]"] == 1
    assert oor["annual_income <= 0"] == 1
    assert oor["annual_income >= 20000000"] == 1
    assert oor["years_employed > age - 14"] == 1


def test_cli_writes_reports(raw_csv: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"
    profiling.main(["--input", str(raw_csv), "--output-dir", str(out_dir)])
    assert json.loads((out_dir / "data_profile.json").read_text(encoding="utf-8"))["rows"] == 5
    assert "## b. Missing values" in (out_dir / "data_profile.md").read_text(encoding="utf-8")
