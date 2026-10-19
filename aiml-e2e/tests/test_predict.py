"""Tests for LoanOfferPredictor, using a model trained on synthetic data."""

from pathlib import Path

import pandas as pd
import pytest

from northwind_loans.cleaning import standardize_frame
from northwind_loans.config import SAMPLE_DATA
from northwind_loans.predict import OUTPUT_COLUMNS, LoanOfferPredictor, main
from northwind_loans.profiling import read_raw_csv

BASE = {
    "application_id": " nwf-100 ", "application_date": "2024-05-01", "age": "35",
    "gender": "M", "marital_status": "Married", "dependents": "1", "education": "UG",
    "city": "Bombay", "employment_type": "salaried", "years_employed": "8",
    "annual_income": "1200000", "existing_loans_count": "1", "monthly_existing_emi": "10000",
    "credit_score": "760", "loan_purpose": "Home Loan", "requested_amount": "3000000",
    "requested_tenure_months": "240", "has_collateral": "Y",
}


def record(**changes: str) -> dict:
    return {**BASE, **changes}


@pytest.fixture(scope="module")
def predictor(trained_model_dir: Path) -> LoanOfferPredictor:
    return LoanOfferPredictor(model_dir=trained_model_dir)


@pytest.fixture(scope="module")
def frame_result(predictor: LoanOfferPredictor) -> pd.DataFrame:
    rows = [
        record(),                                                   # 0 normal
        record(application_id="NWF-101", annual_income="Rs. 5,00,000"),  # 1 text income
        record(application_id="NWF-102", credit_score=""),          # 2 missing score
        record(application_id="NWF-103", credit_score="550"),       # 3 low score
        record(application_id="NWF-104", monthly_existing_emi="80000"),  # 4 dti 0.8
        record(application_id="NWF-105", annual_income=""),         # 5 no income
    ]
    return predictor.predict_frame(pd.DataFrame(rows, dtype=str))


def test_output_columns_and_order(frame_result: pd.DataFrame, predictor: LoanOfferPredictor) -> None:
    assert list(frame_result.columns) == OUTPUT_COLUMNS
    assert frame_result.application_id.tolist()[:2] == ["NWF-100", "NWF-101"]  # cleaned ids
    assert (frame_result.model_version == predictor.model_version).all()


def test_offers_respect_business_rules(frame_result: pd.DataFrame) -> None:
    incomes = [1_200_000, 500_000, 1_200_000, 1_200_000, 1_200_000]
    for offer, income in zip(frame_result.offered_amount[:5], incomes):
        assert 0 <= offer <= 5 * income and offer % 1000 == 0


def test_manual_review_reasons(frame_result: pd.DataFrame) -> None:
    reasons = frame_result.review_reasons.tolist()
    assert reasons[0] == [] and not frame_result.manual_review[0]
    assert reasons[2] == ["credit_score_missing"]
    assert reasons[3] == ["credit_score_below_600"]
    assert reasons[4] == ["dti_above_0.6"]
    assert frame_result.manual_review[2:].all()
    assert pd.notna(frame_result.offered_amount[3])  # flagged but still offered


def test_all_sample_rows_respect_business_rules(predictor: LoanOfferPredictor) -> None:
    raw = read_raw_csv(SAMPLE_DATA)
    predictions = predictor.predict_frame(raw)
    income = standardize_frame(raw)[0]["annual_income"]
    assert len(predictions) == 10
    for offer, inc in zip(predictions.offered_amount, income):
        assert pd.isna(offer) or (0 <= offer <= 5 * inc and offer % 1000 == 0)


def test_credit_score_580_triggers_manual_review(predictor: LoanOfferPredictor) -> None:
    result = predictor.predict_one(record(credit_score="580"))
    assert result["manual_review"] is True
    assert result["review_reasons"] == ["credit_score_below_600"]
    assert result["offered_amount"] is not None  # still offered, just flagged


def test_missing_income_gives_no_offer(frame_result: pd.DataFrame) -> None:
    row = frame_result.iloc[5]
    assert pd.isna(row.offered_amount) and pd.isna(row.raw_model_estimate)
    assert row.review_reasons == ["annual_income_missing"] and row.manual_review
    assert row.rules_applied == []


def test_predict_one_returns_plain_python(predictor: LoanOfferPredictor) -> None:
    result = predictor.predict_one(record(credit_score=""))
    assert set(result) == set(OUTPUT_COLUMNS)
    assert isinstance(result["offered_amount"], int)
    assert isinstance(result["raw_model_estimate"], int)
    assert result["manual_review"] is True
    assert result["review_reasons"] == ["credit_score_missing"]
    assert predictor.predict_one(record(annual_income=""))["offered_amount"] is None


def test_predict_one_with_missing_keys(predictor: LoanOfferPredictor) -> None:
    minimal = {key: BASE[key] for key in ("annual_income", "monthly_existing_emi",
                                          "credit_score", "requested_tenure_months",
                                          "employment_type", "loan_purpose")}
    result = predictor.predict_one(minimal)
    assert result["application_id"] is None and isinstance(result["offered_amount"], int)


def test_predict_records_keeps_order(predictor: LoanOfferPredictor) -> None:
    results = predictor.predict_records([record(application_id="A-1"), record(application_id="B-2")])
    assert [r["application_id"] for r in results] == ["A-1", "B-2"]


def test_cli_writes_csv(trained_model_dir: Path, tmp_path: Path,
                        capsys: pytest.CaptureFixture) -> None:
    model_dir = trained_model_dir
    source = tmp_path / "in.csv"
    pd.DataFrame([record(max_loan_offered="2000000"), record(annual_income="")]).to_csv(
        source, index=False)
    out = tmp_path / "out.csv"
    main(["--input", str(source), "--output", str(out), "--model-dir", str(model_dir)])
    written = pd.read_csv(out, keep_default_na=False)
    assert list(written.columns) == OUTPUT_COLUMNS
    assert written.review_reasons.tolist()[1] == "annual_income_missing"
    assert "diff_%" in capsys.readouterr().out
