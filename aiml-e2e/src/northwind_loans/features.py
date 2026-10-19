"""Credit-policy feature engineering and the column lists the model uses.

`PolicyFeatures` is a STATELESS scikit-learn transformer: it applies the
Northwind credit policy (config.CREDIT_POLICY) row by row. fit() learns
nothing from the data - it only records the input column names.

Preview on the processed data:
    python -m northwind_loans.features [--input PATH]
"""

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from northwind_loans.config import CREDIT_POLICY, LOG_LEVEL, PROCESSED_DATA, RANDOM_STATE, TARGET

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Column lists used by the model (imported by later steps)
# --------------------------------------------------------------------------
RAW_NUMERIC_INPUTS: list[str] = [
    "annual_income",
    "monthly_existing_emi",
    "credit_score",
    "requested_tenure_months",
    "years_employed",
]
RAW_CATEGORICAL_INPUTS: list[str] = ["employment_type", "loan_purpose"]
ENGINEERED_NUMERIC: list[str] = [
    "dti",
    "emi_capacity_amount",
    "policy_cap",
    "affordable_amount",
    "policy_amount",
]
MODEL_CATEGORICAL: list[str] = ["employment_type", "loan_purpose", "credit_band"]

_PROTECTED = "protected or proxy attributes: monitored for fairness, never used"
EXCLUDED_FEATURES: dict[str, str] = {
    "requested_amount": "anchoring and leakage risk: the offer must reflect capacity, not the ask",
    "gender": _PROTECTED,
    "age": _PROTECTED,
    "marital_status": _PROTECTED,
    "dependents": _PROTECTED,
    "city": "possible proxies; excluded in v1",
    "education": "possible proxies; excluded in v1",
    "application_id": "identifiers",
    "application_date": "identifiers",
}

# --------------------------------------------------------------------------
# Policy feature definitions
# --------------------------------------------------------------------------
REQUIRED_INPUTS: list[str] = [
    "annual_income",
    "monthly_existing_emi",
    "credit_score",
    "requested_tenure_months",
    "employment_type",
    "loan_purpose",
]

CREDIT_BANDS: list[str] = ["<600", "600-649", "650-699", "700-749", "750+"]
_BAND_EDGES: list[float] = [-np.inf, 600, 650, 700, 750, np.inf]  # left-inclusive

NEW_FEATURES: list[str] = [
    "monthly_income",
    "dti",
    "credit_band",
    "foir_limit",
    "affordable_emi",
    "annuity_factor",
    "emi_capacity_amount",
    "policy_cap",
    "affordable_amount",
    "credit_haircut",
    "policy_amount",
]


def credit_band(score: pd.Series) -> pd.Series:
    """Map credit scores to bands: 599 -> '<600', 600 -> '600-649', 750 -> '750+'."""
    bands = pd.cut(score, bins=_BAND_EDGES, labels=CREDIT_BANDS, right=False)
    return bands.astype(object)


def annuity_factor(annual_rate_pct: pd.Series, months: pd.Series) -> pd.Series:
    """Present value of 1 rupee of EMI per month: (1 - (1 + r) ** -n) / r."""
    r = annual_rate_pct / 1200
    return (1 - (1 + r) ** -months) / r


def _as_float(series: pd.Series) -> pd.Series:
    """Numeric column as float64 (nullable Int64 NA becomes NaN)."""
    return pd.to_numeric(series, errors="coerce").astype("float64")


class PolicyFeatures(TransformerMixin, BaseEstimator):
    """Add Northwind credit-policy features to a DataFrame (stateless).

    Missing inputs propagate as NaN - nothing is imputed here.

    Parameters
    ----------
    policy : dict or None
        Credit policy to apply; None means config.CREDIT_POLICY.
    """

    def __init__(self, policy: dict | None = None) -> None:
        self.policy = policy

    def fit(self, X: pd.DataFrame, y: object = None) -> "PolicyFeatures":
        """Record the input column names only; nothing is learnt from values."""
        self._check_input(X)
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Return X's columns plus the policy features in NEW_FEATURES."""
        self._check_input(X)
        policy = CREDIT_POLICY if self.policy is None else self.policy
        out = X.copy()

        income = _as_float(X["annual_income"])
        existing_emi = _as_float(X["monthly_existing_emi"])
        score = _as_float(X["credit_score"])
        tenure = _as_float(X["requested_tenure_months"])
        purpose = X["loan_purpose"]

        monthly_income = income / 12
        out["monthly_income"] = monthly_income
        out["dti"] = existing_emi / monthly_income.where(monthly_income > 0)

        band = credit_band(score)
        out["credit_band"] = band

        salaried_bonus = np.where(
            X["employment_type"] == "Salaried", policy["salaried_foir_bonus"], 0.0
        )
        foir_limit = band.map(policy["foir_by_credit_band"]).astype(float) + salaried_bonus
        out["foir_limit"] = foir_limit

        affordable_emi = (monthly_income * foir_limit - existing_emi).clip(lower=0)
        out["affordable_emi"] = affordable_emi

        factor = annuity_factor(purpose.map(policy["rate_card_pct"]).astype(float), tenure)
        out["annuity_factor"] = factor
        out["emi_capacity_amount"] = affordable_emi * factor

        out["policy_cap"] = purpose.map(policy["income_multiple_cap"]).astype(float) * income
        absolute_cap = policy["absolute_cap_income_multiple"] * income
        out["affordable_amount"] = pd.concat(
            [out["emi_capacity_amount"], out["policy_cap"], absolute_cap], axis=1
        ).min(axis=1, skipna=False)

        haircut = band.map(lambda b: policy["credit_haircut"].get(b, 1.0)).astype(float)
        out["credit_haircut"] = haircut
        out["policy_amount"] = out["affordable_amount"] * haircut
        return out

    def get_feature_names_out(self, input_features: object = None) -> np.ndarray:
        """Input column names followed by NEW_FEATURES."""
        if input_features is None:
            input_features = getattr(self, "feature_names_in_", None)
        if input_features is None:
            raise ValueError("Call fit() first or pass input_features.")
        return np.asarray([*input_features, *NEW_FEATURES], dtype=object)

    @staticmethod
    def _check_input(X: object) -> None:
        """Raise a clear error for non-DataFrames or missing required columns."""
        if not isinstance(X, pd.DataFrame):
            raise TypeError(f"PolicyFeatures expects a pandas DataFrame, got {type(X).__name__}")
        missing = [column for column in REQUIRED_INPUTS if column not in X.columns]
        if missing:
            raise ValueError(f"missing required columns: {missing}")


# --------------------------------------------------------------------------
# CLI: preview the features on the processed data
# --------------------------------------------------------------------------
PREVIEW_COLUMNS: list[str] = RAW_NUMERIC_INPUTS + [
    "policy_amount",
    "dti",
    "affordable_emi",
    "affordable_amount",
]


def policy_target_correlation(features_df: pd.DataFrame) -> tuple[int, float, float]:
    """Pearson and Spearman correlation of policy_amount vs the target.

    Uses only rows where all model inputs and the target are present.
    Returns (rows used, pearson, spearman).
    """
    complete = features_df.dropna(subset=RAW_NUMERIC_INPUTS + RAW_CATEGORICAL_INPUTS + [TARGET])
    pearson = complete["policy_amount"].corr(complete[TARGET])
    spearman = complete["policy_amount"].corr(complete[TARGET], method="spearman")
    return len(complete), float(pearson), float(spearman)


def main(argv: list[str] | None = None) -> None:
    """Print a feature preview, the policy/target correlation and a stateless check."""
    parser = argparse.ArgumentParser(description="Preview credit-policy features.")
    parser.add_argument(
        "--input", type=Path, default=PROCESSED_DATA / "loan_applications_raw.parquet"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    pd.set_option("display.width", 250, "display.max_columns", 20)
    pd.set_option("display.float_format", "{:,.2f}".format)

    df = pd.read_parquet(args.input)
    logger.info("Read %s rows from %s", len(df), args.input)
    transformer = PolicyFeatures().set_output(transform="pandas")
    features_df = transformer.fit_transform(df)

    print("First 5 rows:")
    print(features_df.head(5)[PREVIEW_COLUMNS].to_string())

    rows, pearson, spearman = policy_target_correlation(features_df)
    print(f"\npolicy_amount vs {TARGET} ({rows:,} complete rows of {len(df):,}):")
    print(f"  Pearson  {pearson:.4f}\n  Spearman {spearman:.4f}")

    again = transformer.transform(df)
    refit = transformer.fit(df.sample(100, random_state=RANDOM_STATE)).transform(df)
    print("\nStateless check:")
    print(f"  {'transform twice identical':34}: {features_df.equals(again)}")
    print(f"  {'identical after re-fit (100 rows)':34}: {features_df.equals(refit)}")
    print(f"  columns: {df.shape[1]} original + {len(NEW_FEATURES)} new = {features_df.shape[1]}")


if __name__ == "__main__":
    main()
