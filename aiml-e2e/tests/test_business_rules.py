"""Tests for the business rules and manual-review reasons."""

import numpy as np
import pandas as pd

from northwind_loans import business_rules as br


def make_inputs() -> tuple[np.ndarray, pd.DataFrame]:
    raw = np.array([-50_000.0, 1_234_567.0, 9_000_000.0, 500_000.0, 500_000.0, 2_000_000.0])
    X = pd.DataFrame({"annual_income": [600_000.0, 600_000.0, 1_000_000.0, np.nan, 0.0, 800_000.0]})
    return raw, X


def test_rule_names_come_from_policy() -> None:
    assert (br.FLOOR_AT_ZERO, br.CAP_RULE, br.ROUND_RULE) == (
        "floor_at_zero", "cap_5x_income", "round_down_1000")


def test_apply_business_rules() -> None:
    raw, X = make_inputs()
    offers = br.apply_business_rules(raw, X)
    assert offers[:3].tolist() == [
        0.0,          # negative -> floored at 0
        1_234_000.0,  # rounded DOWN to 1000
        5_000_000.0,  # capped at 5 x income
    ]
    assert np.isnan(offers[3]) and np.isnan(offers[4])  # no valid income -> no offer
    assert offers[5] == 2_000_000.0  # already valid and round: unchanged


def test_rules_applied() -> None:
    raw, X = make_inputs()
    assert br.rules_applied(raw, X) == [
        ["floor_at_zero"],
        ["round_down_1000"],
        ["cap_5x_income"],
        [],
        [],
        [],
    ]


def test_review_reasons() -> None:
    X = pd.DataFrame({
        "annual_income": [900_000.0, 900_000.0, 900_000.0, np.nan, 900_000.0],
        "credit_score": [720.0, np.nan, 550.0, 700.0, 600.0],
    })
    dti = pd.Series([0.2, 0.2, 0.7, np.nan, 0.6])
    assert br.review_reasons(X, dti) == [
        [],
        ["credit_score_missing"],
        ["credit_score_below_600", "dti_above_0.6"],
        ["annual_income_missing"],
        [],  # 600 and dti 0.6 are on the boundary -> no review
    ]


def test_count_rule_hits() -> None:
    raw, X = make_inputs()
    assert br.count_rule_hits(raw, X) == {
        "clipped_to_zero": 1,
        "capped_at_income_multiple": 1,
        "no_offer_missing_income": 2,
    }
