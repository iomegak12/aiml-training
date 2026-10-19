"""Tests for scripts/simulate_traffic.py (no network except an unreachable URL)."""

import importlib.util
import random
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from northwind_loans.api.schemas import ApplicantIn
from northwind_loans.config import PROJECT_ROOT

SCRIPT = PROJECT_ROOT / "scripts" / "simulate_traffic.py"
_spec = importlib.util.spec_from_file_location("simulate_traffic", SCRIPT)
sim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sim)

ROW = {
    "application_id": "NWF-1", "annual_income": 1_200_000.0, "monthly_existing_emi": 10_000.0,
    "employment_type": "Salaried", "loan_purpose": "Home", "requested_tenure_months": 240,
    "credit_score": 760, "years_employed": 8.0, "gender": "Female", "age": 34,
}
WEIGHTS = {"Home": 0.42, "Auto": 0.28, "Business": 0.17, "Education": 0.13}


def test_to_payload_drops_missing_and_uses_ints() -> None:
    payload = sim.to_payload({**ROW, "credit_score": np.float64(760.0), "age": None,
                              "years_employed": float("nan")})
    assert payload["credit_score"] == 760 and isinstance(payload["credit_score"], int)
    assert "age" not in payload and "years_employed" not in payload
    assert payload["application_id"] == "NWF-1"
    ApplicantIn(**payload)  # a normal payload is valid


def test_load_applicants_keeps_valid_rows(tmp_path: Path) -> None:
    df = pd.DataFrame([ROW, {**ROW, "application_id": "NWF-2", "annual_income": np.nan}])
    path = tmp_path / "clean.parquet"
    df.to_parquet(path, index=False)
    applicants = sim.load_applicants(path)
    assert [a["application_id"] for a in applicants] == ["NWF-1"]


def test_apply_drift() -> None:
    rng = random.Random(51)
    drifted = sim.apply_drift(ROW, rng, WEIGHTS)
    assert drifted["annual_income"] == pytest.approx(720_000)
    assert drifted["credit_score"] == 680
    assert sim.apply_drift({**ROW, "credit_score": 340}, rng, WEIGHTS)["credit_score"] == 300
    no_score = {k: v for k, v in ROW.items() if k != "credit_score"}
    assert "credit_score" not in sim.apply_drift(no_score, rng, WEIGHTS)
    ApplicantIn(**drifted)  # drifted traffic is still valid


def test_drift_has_half_personal_loans() -> None:
    rng = random.Random(51)
    purposes = [sim.apply_drift(ROW, rng, WEIGHTS)["loan_purpose"] for _ in range(2000)]
    assert purposes.count("Personal") / 2000 == pytest.approx(0.5, abs=0.04)
    assert set(purposes) == {"Personal", *WEIGHTS}


@pytest.mark.parametrize("seed", range(12))
def test_invalid_requests_are_rejected_by_schema(seed: int) -> None:
    kind, bad = sim.make_invalid(ROW, random.Random(seed))
    assert kind in sim.INVALID_KINDS
    with pytest.raises(ValidationError):
        ApplicantIn(**bad)


def test_mode_shares() -> None:
    rng = random.Random(51)
    kinds = [sim.build_request("mixed", [ROW], rng, WEIGHTS)[0] for _ in range(3000)]
    assert kinds.count("normal") / 3000 == pytest.approx(0.7 + 0.1 * 0.7, abs=0.04)
    assert kinds.count("drift") / 3000 == pytest.approx(0.2, abs=0.03)
    bad_kinds = [sim.build_request("bad", [ROW], rng, WEIGHTS)[0] for _ in range(3000)]
    assert bad_kinds.count("bad") / 3000 == pytest.approx(0.3, abs=0.03)


def test_stats_classifies_status_codes() -> None:
    stats = sim.Stats()
    for status in (200, 200, 422, 503, None):
        stats.record("normal", status, 10.0)
    assert stats.sent == 5
    assert stats.by_class == {"2xx": 2, "4xx": 1, "5xx": 1, "errors": 1}
    assert stats.avg_latency_ms() == 10.0


def test_run_never_crashes_on_unreachable_api(tmp_path: Path) -> None:
    path = tmp_path / "clean.parquet"
    pd.DataFrame([ROW]).to_parquet(path, index=False)
    stats = sim.run("http://127.0.0.1:9", "normal", rps=2, duration=0.5, seed=51, data=path)
    assert stats.sent >= 1 and stats.by_class["errors"] == stats.sent
