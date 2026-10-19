"""Reference profile of the training data, stored with each saved model.

Used later for drift checks (PSI) and fairness monitoring. Statistics are
computed on RAW training values (NaN excluded) - the same kind of values the
API will receive.
"""

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from northwind_loans.business_rules import apply_business_rules, count_rule_hits
from northwind_loans.features import PolicyFeatures

PROFILE_NUMERIC: list[str] = [
    "annual_income",
    "credit_score",
    "monthly_existing_emi",
    "requested_tenure_months",
    "dti",
    "predicted_offer",
]
PROFILE_CATEGORICAL: list[str] = ["loan_purpose", "employment_type"]

DECILES = np.linspace(0.1, 0.9, 9)
AGE_BAND_EDGES = [18, 30, 40, 50, np.inf]  # left-inclusive
AGE_BAND_LABELS = ["18-29", "30-39", "40-49", "50+"]


def make_bins(values: object, edges: list[float] | None = None) -> tuple[list[float], list[float]]:
    """Decile bins and the share of values in each bin.

    edges=None : compute interior decile edges from `values`, de-duplicated with
                 np.unique (many zeros or repeated values collapse edges).
    edges=list : reuse stored edges (e.g. to bin live data for PSI).

    Bins are (-inf, e0], (e0, e1], ..., (e_last, +inf) - the outer bins are
    open-ended, so every value lands in a bin. NaN values are ignored.
    """
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if edges is None:
        edges_array = np.unique(np.quantile(v, DECILES)) if v.size else np.array([])
    else:
        edges_array = np.asarray(edges, dtype=float)
    bin_index = np.searchsorted(edges_array, v, side="left")
    counts = np.bincount(bin_index, minlength=edges_array.size + 1)
    shares = counts / v.size if v.size else counts.astype(float)
    return edges_array.tolist(), shares.tolist()


def numeric_summary(values: pd.Series) -> dict:
    """Count, missing share, mean, std and decile bins of one numeric column."""
    numbers = pd.to_numeric(values, errors="coerce").astype("float64")
    present = numbers.dropna()
    edges, shares = make_bins(present)
    return {
        "count": int(present.size),
        "missing_share": float(numbers.isna().mean()),
        "mean": float(present.mean()),
        "std": float(present.std()),
        "bin_edges": edges,
        "bin_shares": shares,
    }


def category_shares(values: pd.Series) -> dict[str, float]:
    """Share of each category (missing values excluded)."""
    return {str(k): float(v) for k, v in values.value_counts(normalize=True).items()}


def age_band(age: pd.Series) -> pd.Series:
    """Age bands 18-29, 30-39, 40-49, 50+."""
    numbers = pd.to_numeric(age, errors="coerce").astype("float64")
    return pd.cut(numbers, bins=AGE_BAND_EDGES, labels=AGE_BAND_LABELS, right=False)


def _group_means(ratio: pd.Series, groups: pd.Series) -> dict[str, dict]:
    """Mean ratio and row count per group (groups with no rows are skipped)."""
    stats = ratio.groupby(groups, observed=True).agg(["mean", "count"])
    return {str(g): {"mean": float(row["mean"]), "count": int(row["count"])}
            for g, row in stats.iterrows()}


def fairness_baseline(X: pd.DataFrame, y: pd.Series) -> dict:
    """Mean of max_loan_offered / annual_income by gender and by age band."""
    income = pd.to_numeric(X["annual_income"], errors="coerce").astype("float64")
    ratio = (y / income.where(income > 0)).dropna()
    return {
        "metric": "mean(max_loan_offered / annual_income)",
        "by_gender": _group_means(ratio, X.loc[ratio.index, "gender"]),
        "by_age_band": _group_means(ratio, age_band(X.loc[ratio.index, "age"])),
    }


def build_reference_profile(X_train: pd.DataFrame, y_train: pd.Series, pipeline: Pipeline) -> dict:
    """Numeric bins, category shares, fairness baseline and business-rule counts."""
    raw_predictions = pipeline.predict(X_train)
    data = X_train.copy()
    data["dti"] = PolicyFeatures().transform(X_train)["dti"]
    data["predicted_offer"] = apply_business_rules(raw_predictions, X_train)
    return {
        "rows": int(len(X_train)),
        "numeric": {column: numeric_summary(data[column]) for column in PROFILE_NUMERIC},
        "categorical": {column: category_shares(data[column]) for column in PROFILE_CATEGORICAL},
        "fairness": fairness_baseline(X_train, y_train),
        "business_rule_counts": count_rule_hits(raw_predictions, X_train),
    }
