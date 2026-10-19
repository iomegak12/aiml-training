"""Tests for make_bins and the fairness baseline."""

import numpy as np
import pandas as pd
import pytest

from northwind_loans.reference_profile import age_band, fairness_baseline, make_bins


def test_make_bins_deciles_on_distinct_values() -> None:
    edges, shares = make_bins(np.arange(1, 101))
    assert len(edges) == 9 and len(shares) == 10
    assert sum(shares) == pytest.approx(1.0)
    assert shares == pytest.approx([0.1] * 10)


def test_make_bins_deduplicates_edges_with_many_zeros() -> None:
    values = np.array([0.0] * 70 + list(range(1, 31)))  # like monthly_existing_emi
    edges, shares = make_bins(values)
    assert edges == sorted(set(edges))  # unique, increasing
    assert edges[0] == 0.0
    assert shares[0] == pytest.approx(0.7)  # all zeros in the first bin (-inf, 0]
    assert sum(shares) == pytest.approx(1.0)


def test_make_bins_ignores_nan_and_reuses_edges() -> None:
    edges, _ = make_bins([1.0, 2.0, 3.0, 4.0, np.nan])
    # live data far outside the training range still lands in the open-ended outer bins
    _, live_shares = make_bins([-1e9, 1e9, 1e9, np.nan], edges=edges)
    assert live_shares[0] == pytest.approx(1 / 3)
    assert live_shares[-1] == pytest.approx(2 / 3)
    assert len(live_shares) == len(edges) + 1


def test_age_bands() -> None:
    bands = age_band(pd.Series([18, 29, 30, 49, 50, 75]))
    assert bands.astype(str).tolist() == ["18-29", "18-29", "30-39", "40-49", "50+", "50+"]


def test_fairness_baseline() -> None:
    X = pd.DataFrame({
        "annual_income": [100.0, 100.0, 200.0, 0.0],
        "gender": ["Male", "Female", "Female", "Male"],
        "age": [25, 35, 35, 60],
    })
    y = pd.Series([300.0, 200.0, 800.0, 999.0])
    result = fairness_baseline(X, y)
    assert result["by_gender"]["Male"] == {"mean": 3.0, "count": 1}  # zero income excluded
    assert result["by_gender"]["Female"] == {"mean": 3.0, "count": 2}
    assert result["by_age_band"]["30-39"]["count"] == 2
