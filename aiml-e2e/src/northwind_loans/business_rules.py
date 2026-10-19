"""Turn raw model predictions into loan offers that respect Northwind's policy.

Offer rules (from config.CREDIT_POLICY), applied in order:
    1. floor_at_zero     -> no negative offers
    2. cap_5x_income     -> at most absolute_cap_income_multiple x annual_income
    3. round_down_1000   -> round DOWN to round_offer_to, e.g. 1,234,567 -> 1,234,000
    No verified income (missing or <= 0) -> no offer at all (NaN / None).

Manual review (CREDIT_POLICY["manual_review_rules"]) flags an application for an
underwriter; the offer is still computed. A missing credit score is flagged
because the model would otherwise impute the median score and could give a
thin-file applicant a prime offer.
"""

import numpy as np
import pandas as pd

from northwind_loans.config import CREDIT_POLICY

_CAP_MULTIPLE = CREDIT_POLICY["absolute_cap_income_multiple"]
_ROUND_TO = CREDIT_POLICY["round_offer_to"]
_REVIEW = CREDIT_POLICY["manual_review_rules"]

# Rule names (used in rules_applied)
FLOOR_AT_ZERO = "floor_at_zero"
CAP_RULE = f"cap_{_CAP_MULTIPLE:g}x_income"
ROUND_RULE = f"round_down_{_ROUND_TO}"

# Review reason codes (used in review_reasons)
INCOME_MISSING = "annual_income_missing"
SCORE_MISSING = "credit_score_missing"
SCORE_LOW = f"credit_score_below_{_REVIEW['credit_score_below']}"
DTI_HIGH = f"dti_above_{_REVIEW['dti_above']:g}"


def _income(X: pd.DataFrame) -> np.ndarray:
    """annual_income as a float array (missing -> NaN)."""
    return pd.to_numeric(X["annual_income"], errors="coerce").to_numpy(dtype=float)


def _no_income(income: np.ndarray) -> np.ndarray:
    """True where income is missing or not positive."""
    return np.isnan(income) | (income <= 0)


def apply_business_rules(raw_predictions: np.ndarray, X: pd.DataFrame) -> np.ndarray:
    """Final offer amounts (INR); NaN where there is no valid income."""
    income = _income(X)
    no_income = _no_income(income)
    cap = _CAP_MULTIPLE * np.where(no_income, 0.0, income)

    offer = np.clip(np.asarray(raw_predictions, dtype=float), 0, None)
    offer = np.minimum(offer, cap)
    offer = np.floor(offer / _ROUND_TO) * _ROUND_TO
    return np.where(no_income, np.nan, offer)


def rules_applied(raw_predictions: np.ndarray, X: pd.DataFrame) -> list[list[str]]:
    """Per row, the names of the rules that changed the amount ([] if none or no income)."""
    income = _income(X)
    result = []
    for raw, inc in zip(np.asarray(raw_predictions, dtype=float), income):
        if np.isnan(inc) or inc <= 0:
            result.append([])
            continue
        rules = []
        value = raw
        if value < 0:
            rules.append(FLOOR_AT_ZERO)
            value = 0.0
        if value > _CAP_MULTIPLE * inc:
            rules.append(CAP_RULE)
            value = _CAP_MULTIPLE * inc
        if value % _ROUND_TO != 0:
            rules.append(ROUND_RULE)
        result.append(rules)
    return result


def review_reasons(X: pd.DataFrame, dti: pd.Series) -> list[list[str]]:
    """Per row, the manual-review reason codes ([] means no review needed).

    X must be the cleaned, NOT imputed, frame so missing values are visible.
    """
    income = _income(X)
    score = pd.to_numeric(X["credit_score"], errors="coerce").to_numpy(dtype=float)
    dti_values = pd.to_numeric(dti, errors="coerce").to_numpy(dtype=float)
    result = []
    for inc, sc, d in zip(income, score, dti_values):
        reasons = []
        if np.isnan(inc) or inc <= 0:
            reasons.append(INCOME_MISSING)
        if np.isnan(sc):
            if _REVIEW["credit_score_missing"]:
                reasons.append(SCORE_MISSING)
        elif sc < _REVIEW["credit_score_below"]:
            reasons.append(SCORE_LOW)
        if not np.isnan(d) and d > _REVIEW["dti_above"]:
            reasons.append(DTI_HIGH)
        result.append(reasons)
    return result


def count_rule_hits(raw_predictions: np.ndarray, X: pd.DataFrame) -> dict[str, int]:
    """How many predictions each rule changed (for metadata and monitoring)."""
    raw = np.asarray(raw_predictions, dtype=float)
    income = _income(X)
    no_income = _no_income(income)
    cap = _CAP_MULTIPLE * income
    return {
        "clipped_to_zero": int((~no_income & (raw < 0)).sum()),
        "capped_at_income_multiple": int((~no_income & (raw > cap)).sum()),
        "no_offer_missing_income": int(no_income.sum()),
    }
