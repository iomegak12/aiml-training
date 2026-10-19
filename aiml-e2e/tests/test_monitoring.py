"""Tests for the monitoring report (PSI drift, fairness screening, CLI exit code)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from northwind_loans import monitoring
from northwind_loans.api.observability import log_predictions
from northwind_loans.config import TARGET
from northwind_loans.predict import LoanOfferPredictor
from northwind_loans.reference_profile import make_bins
from tests.test_train import make_processed

API_FIELDS = ["application_id", "annual_income", "monthly_existing_emi", "employment_type",
              "loan_purpose", "requested_tenure_months", "credit_score", "years_employed",
              "gender", "age"]


# --------------------------------------------------------------------------
# PSI
# --------------------------------------------------------------------------
def test_psi_is_zero_for_identical_shares() -> None:
    assert monitoring.psi([0.2, 0.3, 0.5], [0.2, 0.3, 0.5]) == pytest.approx(0.0)


def test_psi_empty_bin_uses_epsilon_not_infinity() -> None:
    value = monitoring.psi([0.5, 0.5, 0.0], [0.5, 0.0, 0.5])
    assert np.isfinite(value) and value > monitoring.PSI_INVESTIGATE


@pytest.mark.parametrize("value, status", [
    (0.0, "stable"), (0.0999, "stable"), (0.10, "watch"), (0.25, "watch"),
    (0.2501, "investigate"), (None, "no data"),
])
def test_psi_status_thresholds(value: float | None, status: str) -> None:
    assert monitoring.psi_status(value) == status


def reference_for(values: np.ndarray) -> dict:
    edges, shares = make_bins(values)
    return {"bin_edges": edges, "bin_shares": shares, "mean": float(np.mean(values))}


def test_numeric_drift_stable_vs_shifted_income() -> None:
    rng = np.random.default_rng(51)
    reference = {c: reference_for(rng.lognormal(13.5, 0.4, 5000))
                 for c in set(monitoring.DRIFT_FEATURES.values())}
    live = pd.DataFrame({c: rng.lognormal(13.5, 0.4, 1000) for c in monitoring.DRIFT_FEATURES})
    stable = {d["feature"]: d["status"] for d in monitoring.numeric_drift(live, reference)}
    assert set(stable.values()) == {"stable"}

    live["annual_income"] *= 0.6
    drifted = {d["feature"]: d for d in monitoring.numeric_drift(live, reference)}
    assert drifted["annual_income"]["status"] == "investigate"
    assert drifted["credit_score"]["status"] == "stable"


def test_category_drift_includes_unseen_category() -> None:
    df = pd.DataFrame({"loan_purpose": ["Home"] * 50 + ["Holiday"] * 50})
    result = monitoring.category_drift(df, {"Home": 0.5, "Auto": 0.5})
    assert [s["category"] for s in result["shares"]] == ["Home", "Auto", "Holiday"]
    assert result["status"] == "investigate"


# --------------------------------------------------------------------------
# Reading the log
# --------------------------------------------------------------------------
def write_log(path: Path, timestamps: list[str]) -> None:
    lines = [json.dumps({"timestamp": ts, "request_id": f"r{i}", "endpoint": "/predict",
                         "model_version": 1,
                         "input": {"application_id": f"A{i}", "annual_income": 1_200_000,
                                   "monthly_existing_emi": 10_000, "loan_purpose": "Home"},
                         "output": {"offered_amount": 900_000, "manual_review": False}})
             for i, ts in enumerate(timestamps)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_read_prediction_log_flattens_and_filters(tmp_path: Path) -> None:
    log = tmp_path / "predictions.jsonl"
    write_log(log, ["2026-10-16T10:00:00+00:00", "2026-10-16T10:50:00+00:00"])
    now = pd.Timestamp("2026-10-16T11:00:00+00:00")

    everything = monitoring.read_prediction_log(log)
    recent = monitoring.read_prediction_log(log, since_minutes=30, now=now)

    assert len(everything) == 2 and list(recent["application_id"]) == ["A1"]
    assert {"annual_income", "offered_amount", "manual_review"} <= set(everything.columns)
    assert everything["credit_score"].isna().all()  # missing column filled with NaN
    assert monitoring.add_dti(everything)["dti"].iloc[0] == pytest.approx(0.1)


def test_missing_log_gives_empty_frame(tmp_path: Path) -> None:
    assert monitoring.read_prediction_log(tmp_path / "nothing.jsonl").empty


# --------------------------------------------------------------------------
# Fairness
# --------------------------------------------------------------------------
def test_group_ratio_skips_small_groups_and_flags_review() -> None:
    values = pd.Series([1.0] * 40 + [0.7] * 40 + [0.1] * 10)
    groups = pd.Series(["A"] * 40 + ["B"] * 40 + ["C"] * 10)
    result = monitoring.group_ratio(values, groups)
    assert result["ratio"] == pytest.approx(0.7)
    assert result["flag"] == "review" and (result["lowest"], result["highest"]) == ("B", "A")
    assert [g["included"] for g in result["groups"]] == [True, True, False]


def test_group_ratio_needs_two_groups() -> None:
    result = monitoring.group_ratio(pd.Series([1.0] * 40), pd.Series(["A"] * 40))
    assert result["ratio"] is None and result["flag"] == "not enough data"


def test_group_ratio_ok_above_threshold() -> None:
    values = pd.Series([1.0] * 40 + [0.9] * 40)
    groups = pd.Series(["A"] * 40 + ["B"] * 40)
    assert monitoring.group_ratio(values, groups)["flag"] == "ok"


# --------------------------------------------------------------------------
# Whole report + CLI
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def applicants() -> pd.DataFrame:
    """Synthetic applicants (same generator as the training fixture) with IDs."""
    df = make_processed().drop(columns=[TARGET])
    df.insert(0, "application_id", [f"APP-{i:04d}" for i in range(len(df))])
    return df


def write_traffic(log: Path, df: pd.DataFrame, model_dir: Path) -> None:
    """Score applicants and append them to an audit log exactly like the API does."""
    records = df[API_FIELDS].astype(object).where(df[API_FIELDS].notna(), None).to_dict("records")
    results = LoanOfferPredictor(model_dir=model_dir).predict_records(records)
    log_predictions(log, "test", "/predict", 1, records, results)


@pytest.fixture()
def paths(tmp_path: Path, applicants: pd.DataFrame) -> dict[str, Path]:
    data = tmp_path / "applicants.parquet"
    applicants.to_parquet(data, index=False)
    return {"log": tmp_path / "predictions.jsonl", "data": data,
            "output": tmp_path / "reports" / "monitoring_report"}


def run_main(paths: dict[str, Path], model_dir: Path) -> int:
    return monitoring.main(["--log", str(paths["log"]), "--data", str(paths["data"]),
                            "--output", str(paths["output"]), "--model-dir", str(model_dir)])


def test_main_stable_traffic_exit_0(paths: dict[str, Path], applicants: pd.DataFrame,
                                    trained_model_dir: Path) -> None:
    write_traffic(paths["log"], applicants, trained_model_dir)
    assert run_main(paths, trained_model_dir) == 0

    report = json.loads(paths["output"].with_suffix(".json").read_text(encoding="utf-8"))
    assert report["verdict"] == "stable"
    assert report["volumes"]["records"] == len(applicants)
    assert report["volumes"]["matched_for_fairness"] == len(applicants)
    assert set(report["fairness"]) == {"gender", "age_band"}
    markdown = paths["output"].with_suffix(".md").read_text(encoding="utf-8")
    assert "**STABLE**" in markdown and "not a legal test" in markdown


def test_main_drifted_traffic_exit_1(paths: dict[str, Path], applicants: pd.DataFrame,
                                     trained_model_dir: Path) -> None:
    drifted = applicants.copy()
    drifted["annual_income"] *= 0.6
    drifted["credit_score"] = (drifted["credit_score"] - 80).clip(lower=300)
    write_traffic(paths["log"], drifted, trained_model_dir)
    assert run_main(paths, trained_model_dir) == 1

    report = json.loads(paths["output"].with_suffix(".json").read_text(encoding="utf-8"))
    status = {d["feature"]: d["status"] for d in report["drift"]}
    assert status["annual_income"] == "investigate" and status["credit_score"] == "investigate"


def test_main_empty_log_exit_0(paths: dict[str, Path], trained_model_dir: Path) -> None:
    paths["log"].write_text("", encoding="utf-8")
    assert run_main(paths, trained_model_dir) == 0
    report = json.loads(paths["output"].with_suffix(".json").read_text(encoding="utf-8"))
    assert report["verdict"] == "no data"
    assert "NO DATA" in paths["output"].with_suffix(".md").read_text(encoding="utf-8")


def test_audit_log_still_has_no_pii(paths: dict[str, Path], applicants: pd.DataFrame,
                                    trained_model_dir: Path) -> None:
    write_traffic(paths["log"], applicants.head(5), trained_model_dir)
    first = json.loads(paths["log"].read_text(encoding="utf-8").splitlines()[0])
    assert "gender" not in first["input"] and "age" not in first["input"]
