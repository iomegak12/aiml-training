"""Offline monitoring report: data drift, fairness screening and volumes.

Compares the prediction audit log (logs/predictions.jsonl) with the reference
profile stored in the latest model metadata (training data, Step 6).

- Drift    : PSI per feature with the SAME stored decile edges (make_bins).
- Fairness : offer/income and manual-review rate by gender and age band.
             The audit log holds no age/gender (PII), so they are looked up by
             application_id in the processed data - in a real system this would be
             a separate, access-controlled store.
- Volumes  : records, time window, manual-review share.

Usage:
    python -m northwind_loans.monitoring --since-minutes 30 --output reports/monitoring_report

Exit code 1 if any feature is "investigate" (so a scheduled job fails), else 0.

Educational demo on synthetic data - never use for real credit decisions.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from northwind_loans import registry
from northwind_loans.config import LOG_LEVEL, MODEL_DIR, PREDICTION_LOG, PROCESSED_DATA, REPORTS_DIR
from northwind_loans.reference_profile import age_band, category_shares, make_bins

logger = logging.getLogger(__name__)

PSI_EPSILON = 1e-6       # replaces empty-bin shares so log(0) never happens
PSI_WATCH = 0.10         # PSI <  0.10        -> stable
PSI_INVESTIGATE = 0.25   # 0.10 <= PSI <= 0.25 -> watch, > 0.25 -> investigate
FAIRNESS_THRESHOLD = 0.80  # four-fifths rule of thumb (screening only)
MIN_GROUP_SIZE = 30

# live column in the log -> column in the reference profile
DRIFT_FEATURES: dict[str, str] = {
    "annual_income": "annual_income",
    "credit_score": "credit_score",
    "monthly_existing_emi": "monthly_existing_emi",
    "requested_tenure_months": "requested_tenure_months",
    "dti": "dti",
    "offered_amount": "predicted_offer",
}
LOG_NUMERIC: list[str] = ["annual_income", "credit_score", "monthly_existing_emi",
                          "requested_tenure_months", "offered_amount"]
DEFAULT_PROTECTED_DATA = PROCESSED_DATA / "loan_applications_raw.parquet"
DEFAULT_OUTPUT = REPORTS_DIR / "monitoring_report"

FAIRNESS_NOTE = (
    "Screening rule of thumb: for each check we divide the lowest group value by the highest. "
    f"A ratio below {FAIRNESS_THRESHOLD:.2f} is flagged for **review**. The threshold is borrowed "
    "from the US \"four-fifths\" rule for selection rates. It is a prompt to look closer, "
    "**not a legal test** of discrimination. "
    f"Groups with fewer than {MIN_GROUP_SIZE} records are skipped."
)


# --------------------------------------------------------------------------
# Reading the audit log
# --------------------------------------------------------------------------
def flatten_record(record: dict) -> dict:
    """One audit-log line -> one flat row (timestamp + input fields + output fields)."""
    row = {"timestamp": record["timestamp"], "request_id": record.get("request_id")}
    row.update(record.get("input", {}))
    row.update(record.get("output", {}))
    return row


def read_prediction_log(path: Path, since_minutes: float | None = None,
                        now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Audit log as a DataFrame; only records newer than `since_minutes` if given."""
    rows = []
    if path.exists():
        with path.open(encoding="utf-8") as file:
            rows = [flatten_record(json.loads(line)) for line in file if line.strip()]
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    for column in LOG_NUMERIC:
        values = df[column] if column in df else pd.Series(np.nan, index=df.index)
        df[column] = pd.to_numeric(values, errors="coerce").astype("float64")
    if since_minutes is not None:
        now = now if now is not None else pd.Timestamp.now(tz="UTC")
        df = df[df["timestamp"] >= now - pd.Timedelta(minutes=since_minutes)]
    return df.reset_index(drop=True)


def add_dti(df: pd.DataFrame) -> pd.DataFrame:
    """Debt-to-income: monthly EMI / monthly income (same formula as training)."""
    out = df.copy()
    monthly_income = out["annual_income"] / 12
    out["dti"] = out["monthly_existing_emi"] / monthly_income.where(monthly_income > 0)
    return out


def attach_protected_attributes(df: pd.DataFrame, data_path: Path) -> tuple[pd.DataFrame, int]:
    """Look up gender and age by application_id (they are not in the audit log).

    Returns the frame with `gender` and `age` columns and the number of matched rows.
    """
    out = df.drop(columns=["gender", "age"], errors="ignore")
    if "application_id" not in out or not data_path.exists():
        logger.warning("Cannot attach gender/age (no application_id or no %s)", data_path)
        out["gender"], out["age"] = np.nan, np.nan
        return out, 0
    protected = pd.read_parquet(data_path, columns=["application_id", "gender", "age"])
    out = out.merge(protected, on="application_id", how="left", indicator="_match")
    matched = int((out["_match"] == "both").sum())
    return out.drop(columns="_match"), matched


# --------------------------------------------------------------------------
# Drift (PSI)
# --------------------------------------------------------------------------
def psi(expected_shares: list[float], actual_shares: list[float]) -> float:
    """Population Stability Index: sum((actual - expected) * ln(actual / expected))."""
    expected = np.clip(np.asarray(expected_shares, dtype=float), PSI_EPSILON, None)
    actual = np.clip(np.asarray(actual_shares, dtype=float), PSI_EPSILON, None)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def psi_status(value: float | None) -> str:
    """stable (< 0.10), watch (0.10-0.25) or investigate (> 0.25)."""
    if value is None:
        return "no data"
    if value > PSI_INVESTIGATE:
        return "investigate"
    if value >= PSI_WATCH:
        return "watch"
    return "stable"


def _number(value: object, digits: int = 4) -> float | None:
    """Rounded float, or None for NaN/None (keeps the JSON report valid)."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def numeric_drift(df: pd.DataFrame, reference_numeric: dict) -> list[dict]:
    """PSI of each drift feature, binned with the stored training edges."""
    results = []
    for column, reference_column in DRIFT_FEATURES.items():
        reference = reference_numeric[reference_column]
        values = df[column].dropna() if column in df else pd.Series(dtype="float64")
        value = None
        if len(values):
            _, live_shares = make_bins(values, edges=reference["bin_edges"])
            value = psi(reference["bin_shares"], live_shares)
        results.append({
            "feature": column,
            "reference_feature": reference_column,
            "n": int(len(values)),
            "live_mean": _number(values.mean(), 2),
            "reference_mean": _number(reference["mean"], 2),
            "psi": _number(value),
            "status": psi_status(value),
        })
    return results


def category_drift(df: pd.DataFrame, reference_shares: dict[str, float],
                   column: str = "loan_purpose") -> dict:
    """Live vs reference share per category, plus PSI over all categories."""
    live_shares = category_shares(df[column]) if column in df else {}
    categories = list(reference_shares) + [c for c in live_shares if c not in reference_shares]
    expected = [reference_shares.get(c, 0.0) for c in categories]
    actual = [live_shares.get(c, 0.0) for c in categories]
    value = psi(expected, actual) if live_shares else None
    return {
        "feature": column,
        "n": int(df[column].notna().sum()) if column in df else 0,
        "psi": _number(value),
        "status": psi_status(value),
        "shares": [
            {"category": c, "reference": _number(e), "live": _number(a), "difference": _number(a - e)}
            for c, e, a in zip(categories, expected, actual)
        ],
    }


# --------------------------------------------------------------------------
# Fairness screening
# --------------------------------------------------------------------------
def group_ratio(values: pd.Series, groups: pd.Series) -> dict:
    """Mean value per group and the lowest/highest ratio over groups with >= 30 records."""
    stats = values.groupby(groups, observed=True).agg(["mean", "count"])
    group_rows = [
        {"group": str(g), "n": int(row["count"]), "value": _number(row["mean"]),
         "included": bool(row["count"] >= MIN_GROUP_SIZE)}
        for g, row in stats.iterrows()
    ]
    included = stats[stats["count"] >= MIN_GROUP_SIZE]
    result = {"groups": group_rows, "lowest": None, "highest": None, "ratio": None,
              "flag": "not enough data"}
    if len(included) >= 2 and included["mean"].max() > 0:
        result["lowest"] = str(included["mean"].idxmin())
        result["highest"] = str(included["mean"].idxmax())
        ratio = included["mean"].min() / included["mean"].max()
        result["ratio"] = _number(ratio, 3)
        result["flag"] = "review" if ratio < FAIRNESS_THRESHOLD else "ok"
    return result


def fairness_report(df: pd.DataFrame) -> dict:
    """Offer/income and manual-review rate by gender and by age band."""
    income = df["annual_income"]
    offer_to_income = df["offered_amount"] / income.where(income > 0)  # NaN when no offer
    review = df["manual_review"].astype(float)
    by = {"gender": df["gender"], "age_band": age_band(df["age"])}
    return {
        attribute: {
            "offer_to_income": group_ratio(offer_to_income, groups),
            "manual_review_rate": group_ratio(review, groups),
        }
        for attribute, groups in by.items()
    }


def fairness_flags(fairness: dict) -> list[str]:
    """Names of the fairness checks flagged for review, e.g. 'gender / manual_review_rate'."""
    return [f"{attribute} / {check}"
            for attribute, checks in fairness.items()
            for check, result in checks.items() if result["flag"] == "review"]


# --------------------------------------------------------------------------
# Volumes and the whole report
# --------------------------------------------------------------------------
def volumes(df: pd.DataFrame, matched: int) -> dict:
    """Records analysed, time window, manual-review share."""
    return {
        "records": int(len(df)),
        "window_start": df["timestamp"].min().isoformat(),
        "window_end": df["timestamp"].max().isoformat(),
        "model_versions": sorted(int(v) for v in df["model_version"].dropna().unique()),
        "offers_made": int(df["offered_amount"].notna().sum()),
        "manual_review_share": _number(df["manual_review"].astype(float).mean()),
        "matched_for_fairness": matched,
    }


def overall_verdict(drift: list[dict], purpose: dict) -> str:
    """investigate if any feature is investigate, else watch if any is watch, else stable."""
    statuses = [d["status"] for d in drift] + [purpose["status"]]
    for status in ("investigate", "watch"):
        if status in statuses:
            return status
    return "stable"


def build_report(log_path: Path = PREDICTION_LOG, model_dir: Path = MODEL_DIR,
                 data_path: Path = DEFAULT_PROTECTED_DATA, since_minutes: float | None = None,
                 now: pd.Timestamp | None = None) -> dict:
    """Read the log and the latest model's reference profile; return the full report."""
    metadata = registry.load_metadata(model_dir=model_dir)  # JSON only - no pickle loaded
    profile = metadata["reference_profile"]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reference_model_version": metadata["version"],
        "log_file": str(log_path),
        "since_minutes": since_minutes,
        "thresholds": {"psi_watch": PSI_WATCH, "psi_investigate": PSI_INVESTIGATE,
                       "fairness_ratio": FAIRNESS_THRESHOLD, "min_group_size": MIN_GROUP_SIZE},
    }

    df = read_prediction_log(log_path, since_minutes, now)
    if df.empty:
        logger.warning("No prediction records in %s for the selected window", log_path)
        report.update(verdict="no data", volumes={"records": 0}, drift=[],
                      loan_purpose=None, fairness=None, fairness_flags=[])
        return report

    df = add_dti(df)
    df, matched = attach_protected_attributes(df, data_path)
    drift = numeric_drift(df, profile["numeric"])
    purpose = category_drift(df, profile["categorical"]["loan_purpose"])
    fairness = fairness_report(df)
    report.update(
        verdict=overall_verdict(drift, purpose),
        volumes=volumes(df, matched),
        drift=drift,
        loan_purpose=purpose,
        fairness=fairness,
        fairness_flags=fairness_flags(fairness),
    )
    logger.info("Analysed %s records: verdict %s", len(df), report["verdict"])
    return report


# --------------------------------------------------------------------------
# Writing the report
# --------------------------------------------------------------------------
def verdict_text(report: dict) -> str:
    """Plain-English verdict for the top of the Markdown report."""
    if report["verdict"] == "no data":
        return "**NO DATA** - there are no predictions in the log for the selected window."
    features = report["drift"] + [report["loan_purpose"]]
    investigate = [d["feature"] for d in features if d["status"] == "investigate"]
    watch = [d["feature"] for d in features if d["status"] == "watch"]
    if investigate:
        text = (f"**INVESTIGATE** - {', '.join(investigate)} changed strongly compared with the "
                f"training data (PSI > {PSI_INVESTIGATE}). Check the data source and the applicant "
                "population before trusting the offers; consider retraining.")
    elif watch:
        text = (f"**WATCH** - {', '.join(watch)} shifted moderately "
                f"(PSI {PSI_WATCH}-{PSI_INVESTIGATE}). No action yet; keep monitoring.")
    else:
        text = f"**STABLE** - live traffic looks like the training data (every PSI < {PSI_WATCH})."
    if watch and investigate:
        text += f" Also on watch: {', '.join(watch)}."
    flags = report["fairness_flags"]
    if flags:
        text += f"\n\nFairness screening flagged {len(flags)} check(s) for review: {', '.join(flags)}."
    else:
        text += f"\n\nFairness screening: no check fell below {FAIRNESS_THRESHOLD:.2f}."
    return text


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    """Markdown table lines."""
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join("" if v is None else str(v) for v in row) + " |" for row in rows]
    return lines


def _fmt(value: float | None, pattern: str = "{:,.2f}") -> str:
    return "n/a" if value is None else pattern.format(value)


def _fairness_section(title: str, result: dict, pattern: str) -> list[str]:
    """One fairness table plus its ratio line."""
    rows = [[g["group"], g["n"], _fmt(g["value"], pattern),
             "yes" if g["included"] else f"skipped (< {MIN_GROUP_SIZE})"]
            for g in result["groups"]]
    lines = [f"#### {title}", ""] + _table(["Group", "n", "Value", "Included"], rows) + [""]
    if result["ratio"] is None:
        lines.append(f"Ratio lowest / highest: n/a - **{result['flag']}**")
    else:
        lines.append(f"Ratio lowest / highest: **{result['ratio']:.3f}** "
                     f"({result['lowest']} vs {result['highest']}) - **{result['flag']}**")
    return lines + [""]


def to_markdown(report: dict) -> str:
    """Readable Markdown version of the report."""
    lines = ["# Monitoring report - Northwind loan offer model", "",
             "> Educational demonstration on synthetic data - never use for real credit decisions.",
             "", "## Verdict", "", verdict_text(report), ""]
    window = (f"last {report['since_minutes']:g} minutes" if report["since_minutes"] is not None
              else "whole log")
    lines += [f"Generated {report['generated_at']} | reference model "
              f"v{report['reference_model_version']} | window: {window} | log `{report['log_file']}`",
              ""]
    if report["verdict"] == "no data":
        return "\n".join(lines)

    v = report["volumes"]
    lines += ["## Volumes", ""] + _table(["Metric", "Value"], [
        ["Records analysed", f"{v['records']:,}"],
        ["First record (UTC)", v["window_start"]],
        ["Last record (UTC)", v["window_end"]],
        ["Model versions in log", ", ".join(f"v{m}" for m in v["model_versions"])],
        ["Offers made", f"{v['offers_made']:,}"],
        ["Flagged for manual review", f"{v['manual_review_share']:.1%}"],
        ["Matched to gender/age by application_id", f"{v['matched_for_fairness']:,}"],
    ]) + [""]

    lines += ["## Data drift (PSI)", "",
              f"PSI < {PSI_WATCH} stable | {PSI_WATCH}-{PSI_INVESTIGATE} watch | "
              f"> {PSI_INVESTIGATE} investigate. Live values are binned with the training decile "
              "edges stored in the model metadata.", ""]
    lines += _table(["Feature", "Reference", "n", "Live mean", "Reference mean", "PSI", "Status"], [
        [d["feature"], d["reference_feature"], d["n"], _fmt(d["live_mean"]),
         _fmt(d["reference_mean"]), _fmt(d["psi"], "{:.4f}"), d["status"]]
        for d in report["drift"]
    ]) + [""]

    p = report["loan_purpose"]
    lines += ["## Loan purpose shares", ""] + _table(["Category", "Reference", "Live", "Difference"], [
        [s["category"], _fmt(s["reference"], "{:.1%}"), _fmt(s["live"], "{:.1%}"),
         _fmt(s["difference"], "{:+.1%}")]
        for s in p["shares"]
    ]) + ["", f"PSI {_fmt(p['psi'], '{:.4f}')} - **{p['status']}**", ""]

    lines += ["## Fairness screening", "", FAIRNESS_NOTE, ""]
    titles = {"offer_to_income": ("Mean offered amount / annual income", "{:.3f}"),
              "manual_review_rate": ("Manual review rate", "{:.1%}")}
    for attribute, checks in report["fairness"].items():
        lines += [f"### By {attribute}", ""]
        for check, result in checks.items():
            title, pattern = titles[check]
            lines += _fairness_section(title, result, pattern)
    return "\n".join(lines)


def write_report(report: dict, output: Path) -> tuple[Path, Path]:
    """Write <output>.md and <output>.json; returns both paths."""
    output.parent.mkdir(parents=True, exist_ok=True)
    md_path, json_path = output.with_suffix(".md"), output.with_suffix(".json")
    md_path.write_text(to_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    logger.info("Wrote %s and %s", md_path, json_path)
    return md_path, json_path


def exit_code(report: dict) -> int:
    """1 if any feature needs investigation, else 0."""
    return 1 if report["verdict"] == "investigate" else 0


def main(argv: list[str] | None = None) -> int:
    """Build the monitoring report, print a short summary and return the exit code."""
    parser = argparse.ArgumentParser(description="Drift and fairness report from the audit log.")
    parser.add_argument("--since-minutes", type=float, default=None,
                        help="only records newer than this (default: whole log)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="output path without suffix (.md and .json are written)")
    parser.add_argument("--log", type=Path, default=PREDICTION_LOG)
    parser.add_argument("--data", type=Path, default=DEFAULT_PROTECTED_DATA,
                        help="processed data with application_id, gender, age")
    parser.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    args = parser.parse_args(argv)

    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    report = build_report(args.log, args.model_dir, args.data, args.since_minutes)
    md_path, json_path = write_report(report, args.output)

    print(f"Verdict: {report['verdict'].upper()} | records: {report['volumes']['records']:,}")
    for d in report["drift"] + ([report["loan_purpose"]] if report["loan_purpose"] else []):
        print(f"  {d['feature']:<24} PSI {_fmt(d['psi'], '{:7.4f}')}  {d['status']}")
    if report["fairness_flags"]:
        print(f"Fairness checks flagged for review: {', '.join(report['fairness_flags'])}")
    print(f"Report: {md_path} | {json_path}")
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
