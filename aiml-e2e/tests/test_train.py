"""Tests for the training pipelines, using small synthetic data."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from northwind_loans import train
from northwind_loans.config import MODEL_DIR, RANDOM_STATE, TARGET
from northwind_loans.features import PolicyFeatures

N_ROWS = 400


def make_processed(n: int = N_ROWS) -> pd.DataFrame:
    """Synthetic 'cleaned' data whose target follows the credit policy plus noise."""
    rng = np.random.default_rng(RANDOM_STATE)
    df = pd.DataFrame(
        {
            "annual_income": rng.uniform(3e5, 3e6, n),
            "monthly_existing_emi": rng.uniform(0, 3e4, n),
            "credit_score": pd.array(rng.integers(550, 850, n), dtype="Int64"),
            "requested_tenure_months": pd.array(rng.choice([12, 36, 60, 120, 240], n), dtype="Int64"),
            "years_employed": rng.uniform(0, 20, n),
            "employment_type": rng.choice(["Salaried", "Self-Employed", "Business Owner"], n),
            "loan_purpose": rng.choice(["Home", "Personal", "Auto", "Education", "Business"], n),
            "requested_amount": rng.uniform(1e5, 5e6, n),
            "gender": rng.choice(["Male", "Female", "Other"], n),
            "age": pd.array(rng.integers(21, 70, n), dtype="Int64"),
        }
    )
    policy = PolicyFeatures().transform(df)["policy_amount"]
    df[TARGET] = policy * rng.normal(1.0, 0.03, n)
    df.loc[:4, TARGET] = np.nan  # 5 missing targets
    df.loc[10:12, "credit_score"] = pd.NA  # some missing inputs for the imputer
    return df


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("processed")
    make_processed().to_parquet(folder / "part.parquet", index=False)
    return folder


@pytest.fixture(scope="module")
def trained(data_dir: Path) -> tuple[Pipeline, dict]:
    return train.train_and_evaluate(data_dir)


def test_missing_target_dropped_and_split(trained: tuple[Pipeline, dict]) -> None:
    data = trained[1]["data"]
    assert data["rows_loaded"] == N_ROWS
    assert data["target_missing_dropped"] == 5
    assert data["train_rows"] + data["test_rows"] == N_ROWS - 5
    assert data["test_rows"] == round((N_ROWS - 5) * train.TEST_SIZE)


def test_returns_fitted_engineered_pipeline(trained: tuple[Pipeline, dict]) -> None:
    pipe, _ = trained
    assert list(pipe.named_steps) == ["impute", "features", "preprocess", "model"]
    predictions = pipe.predict(make_processed(20).drop(columns=[TARGET]))
    assert predictions.shape == (20,) and np.isfinite(predictions).all()


def test_metrics_present_and_engineered_wins(trained: tuple[Pipeline, dict]) -> None:
    report = trained[1]
    for name in ("engineered", "baseline"):
        assert set(report["cv"][name]) == {"r2", "rmse", "mae"}
        assert set(report["test"][name]) == {"r2", "rmse", "mae"}
        assert report["cv"][name]["rmse"]["mean"] > 0  # sign flipped back
    assert report["cv"]["engineered"]["r2"]["mean"] > report["cv"]["baseline"]["r2"]["mean"]


def test_coefficients_match_features(trained: tuple[Pipeline, dict]) -> None:
    pipe, report = trained
    coefs = report["engineered_coefficients"]["coefficients"]
    assert len(coefs) == len(pipe.named_steps["model"].coef_) == 20  # 10 numeric + 2 + 4 + 4
    assert abs(coefs[0]["coef"]) >= abs(coefs[-1]["coef"])
    assert "policy_amount" in {c["feature"] for c in coefs}
    references = report["engineered_coefficients"]["reference_categories"]
    assert set(references) == {"employment_type", "loan_purpose", "credit_band"}


def test_metadata_contents(trained: tuple[Pipeline, dict]) -> None:
    pipe, report = trained
    metadata = train.build_metadata(report, pipe)
    assert set(metadata["metrics"]) == {"cv", "train", "test"}
    assert metadata["excluded_features"]["requested_amount"].startswith("anchoring")
    assert metadata["credit_policy"]["round_offer_to"] == 1000
    profile = metadata["reference_profile"]
    assert set(profile["numeric"]) >= {"annual_income", "credit_score", "dti", "predicted_offer"}
    assert set(profile["fairness"]["by_age_band"]) <= {"18-29", "30-39", "40-49", "50+"}


def test_cli_writes_reports_and_saves_model(data_dir: Path, tmp_path: Path) -> None:
    real_models_before = sorted(MODEL_DIR.iterdir())
    model_dir = tmp_path / "models"
    train.main(["--data-dir", str(data_dir), "--report-dir", str(tmp_path),
                "--model-dir", str(model_dir)])
    assert (tmp_path / "training_report.json").is_file()
    assert "## Comparison" in (tmp_path / "training_report.md").read_text(encoding="utf-8")
    assert (model_dir / "loan_offer_model_v1.pkl").is_file()
    assert (model_dir / "loan_offer_model_v1.json").is_file()
    assert sorted(MODEL_DIR.iterdir()) == real_models_before  # real models/ untouched
