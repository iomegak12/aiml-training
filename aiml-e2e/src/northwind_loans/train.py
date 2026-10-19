"""Train and compare the engineered and baseline LinearRegression pipelines.

Usage:
    python -m northwind_loans.train [--data-dir DIR] [--report-dir DIR] [--model-dir DIR]

Writes reports/training_report.json and .md, and saves the engineered
pipeline as the next version in models/ (with signed metadata).
"""

import argparse
import copy
import json
import logging
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from northwind_loans import registry
from northwind_loans.config import (
    CREDIT_POLICY,
    LOG_LEVEL,
    MODEL_DIR,
    PROCESSED_DATA,
    RANDOM_STATE,
    REPORTS_DIR,
    TARGET,
)
from northwind_loans.features import (
    ENGINEERED_NUMERIC,
    EXCLUDED_FEATURES,
    MODEL_CATEGORICAL,
    RAW_CATEGORICAL_INPUTS,
    RAW_NUMERIC_INPUTS,
    PolicyFeatures,
)
from northwind_loans.reference_profile import build_reference_profile

logger = logging.getLogger(__name__)

TEST_SIZE = 0.2
CV_FOLDS = 5
TOP_COEFFICIENTS = 8

# sklearn scorer name -> our metric name (neg_* scores are flipped back to positive)
SCORING: dict[str, str] = {
    "r2": "r2",
    "rmse": "neg_root_mean_squared_error",
    "mae": "neg_mean_absolute_error",
}


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
def load_processed(data_dir: Path) -> pd.DataFrame:
    """Read and concatenate every cleaned parquet file in data_dir."""
    paths = sorted(data_dir.glob("*.parquet"))
    if not paths:
        raise FileNotFoundError(f"no parquet files in {data_dir} - run `make clean-data` first")
    df = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    logger.info("Loaded %s rows from %s file(s)", len(df), len(paths))
    return df


def drop_missing_target(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop rows whose target is missing; return (df, rows dropped)."""
    missing = df[TARGET].isna()
    return df[~missing].reset_index(drop=True), int(missing.sum())


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """80/20 train/test split with the configured random state."""
    X = df.drop(columns=[TARGET])
    y = df[TARGET]
    return train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE)


# --------------------------------------------------------------------------
# Pipelines
# --------------------------------------------------------------------------
def make_imputer() -> ColumnTransformer:
    """Median for raw numerics, most frequent for raw categoricals.

    Outputs a DataFrame with the original column names (needed by PolicyFeatures).
    """
    imputer = ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median"), RAW_NUMERIC_INPUTS),
            ("cat", SimpleImputer(strategy="most_frequent"), RAW_CATEGORICAL_INPUTS),
        ],
        verbose_feature_names_out=False,
    )
    return imputer.set_output(transform="pandas")


def make_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    """Scale numerics; one-hot encode categoricals (first level dropped)."""
    return ColumnTransformer(
        [
            ("num", StandardScaler(), numeric),
            (
                "cat",
                OneHotEncoder(drop="first", handle_unknown="ignore", sparse_output=False),
                categorical,
            ),
        ],
        verbose_feature_names_out=False,
    )


def make_engineered_pipeline() -> Pipeline:
    """Production candidate: impute -> policy features -> preprocess -> LinearRegression."""
    return Pipeline(
        [
            ("impute", make_imputer()),
            ("features", PolicyFeatures()),
            ("preprocess", make_preprocessor(RAW_NUMERIC_INPUTS + ENGINEERED_NUMERIC,
                                             MODEL_CATEGORICAL)),
            ("model", LinearRegression()),
        ]
    )


def make_baseline_pipeline() -> Pipeline:
    """Baseline: same imputation and encoding, raw inputs only, no policy features."""
    return Pipeline(
        [
            ("impute", make_imputer()),
            ("preprocess", make_preprocessor(RAW_NUMERIC_INPUTS, RAW_CATEGORICAL_INPUTS)),
            ("model", LinearRegression()),
        ]
    )


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------
def cross_validate_pipeline(pipe: Pipeline, X: pd.DataFrame, y: pd.Series) -> dict[str, dict]:
    """5-fold shuffled KFold CV; returns {metric: {"mean", "std"}} (RMSE/MAE positive)."""
    folds = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    scores = cross_validate(pipe, X, y, cv=folds, scoring=SCORING)
    result = {}
    for metric, scorer in SCORING.items():
        values = scores[f"test_{metric}"]
        if scorer.startswith("neg_"):
            values = -values
        result[metric] = {"mean": float(values.mean()), "std": float(values.std())}
    return result


def score_metrics(pipe: Pipeline, X: pd.DataFrame, y: pd.Series) -> dict[str, float]:
    """R2, RMSE and MAE of a fitted pipeline on (X, y)."""
    predictions = pipe.predict(X)
    return {
        "r2": float(r2_score(y, predictions)),
        "rmse": float(root_mean_squared_error(y, predictions)),
        "mae": float(mean_absolute_error(y, predictions)),
    }


def coefficients(pipe: Pipeline) -> dict:
    """Intercept, coefficients (with feature names) sorted by |coef|, and the
    dropped one-hot reference category per column (dummies are relative to it)."""
    preprocess = pipe.named_steps["preprocess"]
    names = preprocess.get_feature_names_out()
    model = pipe.named_steps["model"]
    pairs = sorted(zip(names, model.coef_), key=lambda pair: abs(pair[1]), reverse=True)
    encoder = preprocess.named_transformers_["cat"]
    references = {
        str(column): str(categories[index])
        for column, categories, index in zip(
            encoder.feature_names_in_, encoder.categories_, encoder.drop_idx_
        )
    }
    return {
        "intercept": float(model.intercept_),
        "reference_categories": references,
        "coefficients": [{"feature": str(name), "coef": float(coef)} for name, coef in pairs],
    }


def train_and_evaluate(data_dir: Path = PROCESSED_DATA) -> tuple[Pipeline, dict]:
    """Train both pipelines, evaluate them, and return (fitted engineered pipeline, report)."""
    df = load_processed(data_dir)
    rows_loaded = len(df)
    df, target_missing = drop_missing_target(df)
    X_train, X_test, y_train, y_test = split(df)

    pipelines = {"engineered": make_engineered_pipeline(), "baseline": make_baseline_pipeline()}
    cv_results, train_results, test_results = {}, {}, {}
    for name, pipe in pipelines.items():
        logger.info("Cross-validating %s pipeline", name)
        cv_results[name] = cross_validate_pipeline(pipe, X_train, y_train)
        pipe.fit(X_train, y_train)
        train_results[name] = score_metrics(pipe, X_train, y_train)
        test_results[name] = score_metrics(pipe, X_test, y_test)

    engineered = pipelines["engineered"]
    report = {
        "data": {
            "rows_loaded": rows_loaded,
            "target_missing_dropped": target_missing,
            "target_zero_kept": int((df[TARGET] == 0).sum()),
            "train_rows": len(X_train),
            "test_rows": len(X_test),
        },
        "settings": {
            "test_size": TEST_SIZE,
            "cv_folds": CV_FOLDS,
            "shuffle": True,
            "random_state": RANDOM_STATE,
        },
        "cv": cv_results,
        "train": train_results,
        "test": test_results,
        "engineered_coefficients": coefficients(engineered),
        "reference_profile": build_reference_profile(X_train, y_train, engineered),
    }
    return engineered, report


def build_metadata(report: dict, pipeline: Pipeline) -> dict:
    """Metadata saved next to the model (the registry adds name, version, hashes)."""
    encoded = pipeline.named_steps["preprocess"].get_feature_names_out()
    return {
        "target": TARGET,
        "train_rows": report["data"]["train_rows"],
        "test_rows": report["data"]["test_rows"],
        "raw_input_columns": RAW_NUMERIC_INPUTS + RAW_CATEGORICAL_INPUTS,
        "model_feature_columns": RAW_NUMERIC_INPUTS + ENGINEERED_NUMERIC + MODEL_CATEGORICAL,
        "encoded_feature_names": [str(name) for name in encoded],
        "excluded_features": dict(EXCLUDED_FEATURES),
        "metrics": {
            "cv": report["cv"]["engineered"],
            "train": report["train"]["engineered"],
            "test": report["test"]["engineered"],
        },
        "training_settings": report["settings"],
        "credit_policy": copy.deepcopy(CREDIT_POLICY),
        "reference_profile": report["reference_profile"],
    }


# --------------------------------------------------------------------------
# Reports and CLI
# --------------------------------------------------------------------------
def comparison_rows(report: dict) -> list[list[str]]:
    """One row per pipeline: CV mean +/- std and test metrics, formatted."""
    rows = []
    for name in report["cv"]:
        cv, test = report["cv"][name], report["test"][name]
        rows.append([
            name,
            f"{cv['r2']['mean']:.4f} ± {cv['r2']['std']:.4f}",
            f"{cv['rmse']['mean']:,.0f} ± {cv['rmse']['std']:,.0f}",
            f"{cv['mae']['mean']:,.0f} ± {cv['mae']['std']:,.0f}",
            f"{test['r2']:.4f}",
            f"{test['rmse']:,.0f}",
            f"{test['mae']:,.0f}",
        ])
    return rows


COMPARISON_HEADERS = ["Pipeline", "CV R²", "CV RMSE (INR)", "CV MAE (INR)",
                      "Test R²", "Test RMSE", "Test MAE"]


def write_reports(report: dict, out_dir: Path) -> tuple[Path, Path]:
    """Write training_report.json and training_report.md; return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "training_report.json"
    md_path = out_dir / "training_report.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    data, settings = report["data"], report["settings"]
    coefs = report["engineered_coefficients"]
    lines = [
        "# Training Report",
        "",
        "> Educational demo on synthetic data - never use for real credit decisions.",
        "",
        "## Data",
        "",
        "| Item | Value |",
        "|---|---|",
        *[f"| {key} | {value:,} |" for key, value in data.items()],
        "",
        f"Split {1 - settings['test_size']:.0%}/{settings['test_size']:.0%}, "
        f"{settings['cv_folds']}-fold KFold (shuffle, random_state={settings['random_state']}).",
        "",
        "## Comparison",
        "",
        "| " + " | ".join(COMPARISON_HEADERS) + " |",
        "|" + "---|" * len(COMPARISON_HEADERS),
        *["| " + " | ".join(row) + " |" for row in comparison_rows(report)],
        "",
        "## Engineered model coefficients (scaled features, sorted by |coef|)",
        "",
        f"Intercept: {coefs['intercept']:,.2f}",
        "",
        "One-hot reference (dropped) categories - dummy coefficients are relative to these: "
        + ", ".join(f"{col} = `{ref}`" for col, ref in coefs["reference_categories"].items()),
        "",
        "| Feature | Coefficient |",
        "|---|---|",
        *[f"| {c['feature']} | {c['coef']:,.2f} |" for c in coefs["coefficients"]],
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Wrote %s and %s", json_path, md_path)
    return json_path, md_path


def print_comparison(report: dict) -> None:
    """Print data counts, the comparison table and the top coefficients."""
    data = report["data"]
    print(f"Rows loaded {data['rows_loaded']:,} | target missing dropped "
          f"{data['target_missing_dropped']:,} | target = 0 kept {data['target_zero_kept']:,} | "
          f"train {data['train_rows']:,} | test {data['test_rows']:,}")

    widths = [12, 18, 21, 19, 9, 12, 10]
    print()
    print("".join(f"{h:<{w}}" for h, w in zip(COMPARISON_HEADERS, widths)))
    for row in comparison_rows(report):
        print("".join(f"{cell:<{w}}" for cell, w in zip(row, widths)))

    coefs = report["engineered_coefficients"]
    print(f"\nTop {TOP_COEFFICIENTS} engineered coefficients (scaled features)  "
          f"intercept = {coefs['intercept']:,.0f}")
    for item in coefs["coefficients"][:TOP_COEFFICIENTS]:
        print(f"  {item['feature']:28}{item['coef']:>16,.0f}")
    print(f"  (one-hot reference categories: {coefs['reference_categories']})")


def main(argv: list[str] | None = None) -> None:
    """Train, evaluate, write reports and save the engineered model."""
    parser = argparse.ArgumentParser(description="Train and compare loan-offer pipelines.")
    parser.add_argument("--data-dir", type=Path, default=PROCESSED_DATA)
    parser.add_argument("--report-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    pipeline, report = train_and_evaluate(args.data_dir)
    json_path, md_path = write_reports(report, args.report_dir)
    saved = registry.save_model(pipeline, build_metadata(report, pipeline), args.model_dir)

    print_comparison(report)
    print(f"\nReports: {json_path}\n         {md_path}")
    size_kb = Path(saved["model_path"]).stat().st_size / 1024
    print(f"Saved {saved['model_name']} v{saved['version']}: {saved['model_path']} "
          f"({size_kb:,.1f} KB)\n      metadata: {saved['metadata_path']}")


if __name__ == "__main__":
    main()
