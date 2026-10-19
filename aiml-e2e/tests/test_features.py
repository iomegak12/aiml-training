"""Tests for the credit-policy feature transformer."""

import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone

from northwind_loans import features
from northwind_loans.features import PolicyFeatures


def make_frame() -> pd.DataFrame:
    """Two hand-checkable applicants plus one with a missing credit score."""
    return pd.DataFrame(
        {
            "annual_income": [1_200_000.0, 600_000.0, 900_000.0],
            "monthly_existing_emi": [10_000.0, 5_000.0, 0.0],
            "credit_score": pd.array([760, 610, pd.NA], dtype="Int64"),
            "requested_tenure_months": pd.array([240, 36, 60], dtype="Int64"),
            "years_employed": [8.0, 3.0, 5.0],
            "employment_type": ["Salaried", "Self-Employed", "Salaried"],
            "loan_purpose": ["Home", "Personal", "Auto"],
        }
    )


def expected_annuity(rate_pct: float, months: int) -> float:
    r = rate_pct / 1200
    return (1 - (1 + r) ** -months) / r


def test_salaried_home_loan_by_hand() -> None:
    row = PolicyFeatures().transform(make_frame()).iloc[0]
    assert row.monthly_income == 100_000
    assert row.dti == pytest.approx(0.1)
    assert row.credit_band == "750+"
    assert row.foir_limit == pytest.approx(0.60)  # 0.55 + salaried bonus 0.05
    assert row.affordable_emi == pytest.approx(50_000)
    emi_capacity = 50_000 * expected_annuity(8.6, 240)
    assert row.emi_capacity_amount == pytest.approx(emi_capacity)
    assert row.policy_cap == pytest.approx(6_000_000)  # 5.0 x income
    assert row.affordable_amount == pytest.approx(min(emi_capacity, 6_000_000, 6_000_000))
    assert row.credit_haircut == 1.0
    assert row.policy_amount == pytest.approx(row.affordable_amount)


def test_self_employed_personal_loan_with_haircut() -> None:
    row = PolicyFeatures().transform(make_frame()).iloc[1]
    assert row.credit_band == "600-649"
    assert row.foir_limit == pytest.approx(0.40)  # no salaried bonus
    assert row.affordable_emi == pytest.approx(50_000 * 0.40 - 5_000)
    emi_capacity = 15_000 * expected_annuity(12.5, 36)  # about 4.48 lakh
    assert row.policy_cap == pytest.approx(900_000)  # 1.5 x income
    assert row.affordable_amount == pytest.approx(emi_capacity)  # EMI capacity binds
    assert row.credit_haircut == 0.8
    assert row.policy_amount == pytest.approx(0.8 * emi_capacity)


def test_missing_credit_score_propagates_nan() -> None:
    row = PolicyFeatures().transform(make_frame()).iloc[2]
    assert pd.isna(row.credit_band)
    assert np.isnan(row.foir_limit) and np.isnan(row.policy_amount)


@pytest.mark.parametrize(
    "score, band",
    [(300, "<600"), (599, "<600"), (600, "600-649"), (649, "600-649"),
     (650, "650-699"), (749, "700-749"), (750, "750+"), (900, "750+")],
)
def test_credit_band_edges(score: int, band: str) -> None:
    assert features.credit_band(pd.Series([float(score)])).iloc[0] == band


def test_zero_income_gives_nan_dti() -> None:
    df = make_frame().assign(annual_income=0.0)
    assert PolicyFeatures().transform(df).dti.isna().all()


def test_keeps_original_columns_and_does_not_modify_input() -> None:
    df = make_frame()
    before = df.copy()
    out = PolicyFeatures().transform(df)
    assert list(out.columns) == list(df.columns) + features.NEW_FEATURES
    pd.testing.assert_frame_equal(df, before)


def test_stateless() -> None:
    df = make_frame()
    transformer = PolicyFeatures()
    first = transformer.transform(df)
    assert transformer.fit(df) is transformer
    pd.testing.assert_frame_equal(first, transformer.transform(df))
    transformer.fit(df.assign(annual_income=1.0))  # fitting on other data changes nothing
    pd.testing.assert_frame_equal(first, transformer.transform(df))
    pd.testing.assert_frame_equal(first, clone(transformer).transform(df))


def test_feature_names_and_set_output() -> None:
    df = make_frame()
    transformer = PolicyFeatures().set_output(transform="pandas")
    out = transformer.fit_transform(df)
    assert isinstance(out, pd.DataFrame)
    assert list(transformer.get_feature_names_out()) == list(out.columns)
    assert list(PolicyFeatures().get_feature_names_out(["a"])) == ["a", *features.NEW_FEATURES]


def test_clear_errors() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        PolicyFeatures().transform(make_frame().drop(columns=["credit_score"]))
    with pytest.raises(TypeError):
        PolicyFeatures().transform(make_frame().to_numpy())


def test_cli_preview_runs(tmp_path, capsys) -> None:
    rows = pd.concat([make_frame()] * 40, ignore_index=True)  # >= 100 rows for the re-fit sample
    rows["max_loan_offered"] = range(1, len(rows) + 1)
    path = tmp_path / "processed.parquet"
    rows.to_parquet(path, index=False)
    features.main(["--input", str(path)])
    output = capsys.readouterr().out
    assert "Pearson" in output
    assert output.count("True") == 2


def test_model_columns_do_not_use_excluded_features() -> None:
    used = set(features.RAW_NUMERIC_INPUTS + features.ENGINEERED_NUMERIC
               + features.MODEL_CATEGORICAL)
    assert used.isdisjoint(features.EXCLUDED_FEATURES)
