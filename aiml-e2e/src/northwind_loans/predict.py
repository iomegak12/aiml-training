"""Predict loan offers for new applicants with a saved model.

Flow per applicant (same cleaning as training, no de-duplication):
    raw row -> cleaning.standardize_frame -> pipeline.predict -> business rules
            -> manual-review reasons

Usage:
    python -m northwind_loans.predict [--input CSV] [--output CSV] [--version N]

Educational demo on synthetic data - never use for real credit decisions.
"""

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from northwind_loans import registry
from northwind_loans.business_rules import apply_business_rules, review_reasons, rules_applied
from northwind_loans.cleaning import standardize_frame
from northwind_loans.config import LOG_LEVEL, MODEL_DIR, REPORTS_DIR, SAMPLE_DATA, TARGET
from northwind_loans.features import RAW_CATEGORICAL_INPUTS, PolicyFeatures
from northwind_loans.profiling import ID_COLUMN, read_raw_csv

logger = logging.getLogger(__name__)

OUTPUT_COLUMNS: list[str] = [
    "application_id",
    "offered_amount",
    "raw_model_estimate",
    "manual_review",
    "review_reasons",
    "rules_applied",
    "model_version",
]


def _add_missing_inputs(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Add model input columns that are absent, as missing values."""
    df = df.copy()
    for column in columns:
        if column not in df:
            dtype = object if column in RAW_CATEGORICAL_INPUTS else "float64"
            df[column] = pd.Series(np.nan, index=df.index, dtype=dtype)
    return df


def _to_python(value: object) -> object:
    """Convert pandas/numpy scalars to plain Python (NA -> None)."""
    if isinstance(value, list):
        return value
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


class LoanOfferPredictor:
    """Loads a saved model once and turns applications into loan offers."""

    def __init__(self, version: int | None = None, model_dir: Path = MODEL_DIR) -> None:
        self.pipeline, self.metadata = registry.load_model(version, model_dir)
        self.model_version: int = self.metadata["version"]
        logger.info("Predictor ready with model v%s", self.model_version)

    def predict_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return one row per applicant with the OUTPUT_COLUMNS, in input order."""
        clean, _ = standardize_frame(df)
        clean = _add_missing_inputs(clean, self.metadata["raw_input_columns"])

        raw = self.pipeline.predict(clean)
        offers = apply_business_rules(raw, clean)
        no_offer = np.isnan(offers)
        dti = PolicyFeatures().transform(clean)["dti"]  # on un-imputed values
        reasons = review_reasons(clean, dti)

        ids = clean[ID_COLUMN] if ID_COLUMN in clean else pd.Series(None, index=clean.index)
        return pd.DataFrame(
            {
                "application_id": ids.to_numpy(dtype=object),
                "offered_amount": pd.array(np.where(no_offer, np.nan, offers), dtype="Int64"),
                "raw_model_estimate": pd.array(np.where(no_offer, np.nan, np.round(raw)),
                                               dtype="Int64"),
                "manual_review": [len(r) > 0 for r in reasons],
                "review_reasons": reasons,
                "rules_applied": rules_applied(raw, clean),
                "model_version": self.model_version,
            },
            columns=OUTPUT_COLUMNS,
        )

    def predict_records(self, records: list[dict]) -> list[dict]:
        """Predict for a list of applications (dicts); JSON-friendly results."""
        predictions = self.predict_frame(pd.DataFrame(records))
        return [
            {column: _to_python(row[column]) for column in OUTPUT_COLUMNS}
            for _, row in predictions.iterrows()
        ]

    def predict_one(self, record: dict) -> dict:
        """Predict for a single application given as a dict (JSON-friendly result)."""
        return self.predict_records([record])[0]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def comparison_table(raw: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    """Predictions next to the actual max_loan_offered (if present) and % difference."""
    table = pd.DataFrame({"application_id": predictions["application_id"]})
    if TARGET in raw:
        actual = pd.to_numeric(raw[TARGET].str.replace(",", ""), errors="coerce")
        table["actual"] = pd.array(actual.to_numpy(), dtype="Int64")
    else:
        table["actual"] = pd.array([pd.NA] * len(predictions), dtype="Int64")
    table["offered"] = predictions["offered_amount"]
    actual_float = table["actual"].astype("Float64")
    pct = (table["offered"].astype("Float64") - actual_float) / actual_float.where(actual_float > 0)
    table["diff_%"] = (100 * pct).round(1)
    table["review"] = predictions["manual_review"].map({True: "YES", False: ""})
    table["reasons"] = predictions["review_reasons"].map("; ".join)
    return table


def write_predictions(predictions: pd.DataFrame, path: Path) -> None:
    """Write predictions to CSV (list columns joined with '; ')."""
    out = predictions.copy()
    for column in ("review_reasons", "rules_applied"):
        out[column] = out[column].map("; ".join)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    logger.info("Wrote %s predictions to %s", len(out), path)


def main(argv: list[str] | None = None) -> None:
    """Predict offers for a CSV of applications and print a comparison table."""
    parser = argparse.ArgumentParser(description="Predict loan offers for applicants.")
    parser.add_argument("--input", type=Path, default=SAMPLE_DATA)
    parser.add_argument("--output", type=Path, default=REPORTS_DIR / "sample_predictions.csv")
    parser.add_argument("--version", type=int, default=None, help="model version (default: latest)")
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    raw = read_raw_csv(args.input)
    predictor = LoanOfferPredictor(args.version, args.model_dir)
    predictions = predictor.predict_frame(raw)
    write_predictions(predictions, args.output)

    with pd.option_context("display.width", 200, "display.max_colwidth", 60):
        print(f"Model v{predictor.model_version} | {len(predictions)} applicants | "
              f"{int(predictions['manual_review'].sum())} flagged for manual review\n")
        print(comparison_table(raw, predictions).to_string(index=False))
    print(f"\nPredictions: {args.output}")


if __name__ == "__main__":
    main()
