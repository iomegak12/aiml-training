"""Traffic simulator for the Northwind loan offer API.

Modes:
    normal - real applicants from the cleaned data, sent as they are
    drift  - economic downturn: income x 0.6, credit score - 80 (min 300),
             loan_purpose resampled with Personal at 50%
    bad    - 30% invalid requests (score 1200, negative income, "Holiday",
             missing employment_type), the rest normal
    mixed  - 70% normal, 20% drift, 10% bad

Usage:
    python scripts/simulate_traffic.py --mode normal --rps 5 --duration 120

Educational demo on synthetic data - never use for real credit decisions.
"""

import argparse
import math
import random
import time
from pathlib import Path

import pandas as pd
import requests

from northwind_loans.config import PROCESSED_DATA, RANDOM_STATE

DEFAULT_DATA = PROCESSED_DATA / "loan_applications_raw.parquet"

REQUIRED_FIELDS: list[str] = [
    "annual_income", "monthly_existing_emi", "employment_type", "loan_purpose",
    "requested_tenure_months",
]
OPTIONAL_FIELDS: list[str] = ["application_id", "credit_score", "years_employed", "gender", "age"]
INT_FIELDS = {"requested_tenure_months", "credit_score", "age"}

DRIFT_INCOME_FACTOR = 0.6
DRIFT_SCORE_SHIFT = 80
MIN_CREDIT_SCORE = 300
DRIFT_PERSONAL_SHARE = 0.5
BAD_SHARE = 0.3
MIXED_SHARES: dict[str, float] = {"normal": 0.7, "drift": 0.2, "bad": 0.1}
INVALID_KINDS: list[str] = ["credit_score_1200", "negative_income", "holiday_purpose",
                            "missing_employment_type"]
REPORT_EVERY_S = 10
TIMEOUT_S = 5


# --------------------------------------------------------------------------
# Building requests
# --------------------------------------------------------------------------
def to_payload(row: dict) -> dict:
    """API payload from one cleaned row (missing values are left out)."""
    payload = {}
    for field in REQUIRED_FIELDS + OPTIONAL_FIELDS:
        value = row.get(field)
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            continue
        if field in INT_FIELDS:
            value = int(value)
        elif hasattr(value, "item"):  # numpy scalar -> plain Python for JSON
            value = value.item()
        payload[field] = value
    return payload


def load_applicants(path: Path) -> list[dict]:
    """Rows with all required API fields, as JSON-ready payloads."""
    df = pd.read_parquet(path).dropna(subset=REQUIRED_FIELDS)
    columns = [c for c in REQUIRED_FIELDS + OPTIONAL_FIELDS if c in df.columns]
    rows = df[columns].astype(object).where(df[columns].notna(), None).to_dict("records")
    return [to_payload(row) for row in rows]


def purpose_weights(applicants: list[dict]) -> dict[str, float]:
    """Share of each non-Personal purpose in the data (renormalised to 1)."""
    counts = pd.Series([a["loan_purpose"] for a in applicants]).value_counts()
    others = counts.drop("Personal", errors="ignore")
    return (others / others.sum()).to_dict()


def apply_drift(payload: dict, rng: random.Random, weights: dict[str, float]) -> dict:
    """Economic downturn: lower income and scores, more Personal loans."""
    drifted = dict(payload)
    drifted["annual_income"] = round(payload["annual_income"] * DRIFT_INCOME_FACTOR, 2)
    if payload.get("credit_score") is not None:
        drifted["credit_score"] = max(MIN_CREDIT_SCORE, payload["credit_score"] - DRIFT_SCORE_SHIFT)
    if rng.random() < DRIFT_PERSONAL_SHARE:
        drifted["loan_purpose"] = "Personal"
    else:
        drifted["loan_purpose"] = rng.choices(list(weights), weights=list(weights.values()))[0]
    return drifted


def make_invalid(payload: dict, rng: random.Random) -> tuple[str, dict]:
    """One kind of invalid request (the API must answer 422)."""
    kind = rng.choice(INVALID_KINDS)
    bad = dict(payload)
    if kind == "credit_score_1200":
        bad["credit_score"] = 1200
    elif kind == "negative_income":
        bad["annual_income"] = -abs(payload["annual_income"])
    elif kind == "holiday_purpose":
        bad["loan_purpose"] = "Holiday"
    else:
        bad.pop("employment_type", None)
    return kind, bad


def build_request(mode: str, applicants: list[dict], rng: random.Random,
                  weights: dict[str, float]) -> tuple[str, dict]:
    """(kind, payload) for the next request; kind is normal / drift / bad."""
    if mode == "mixed":
        mode = rng.choices(list(MIXED_SHARES), weights=list(MIXED_SHARES.values()))[0]
    payload = rng.choice(applicants)
    if mode == "drift":
        return "drift", apply_drift(payload, rng, weights)
    if mode == "bad" and rng.random() < BAD_SHARE:
        return "bad", make_invalid(payload, rng)[1]
    return "normal", payload


# --------------------------------------------------------------------------
# Sending and statistics
# --------------------------------------------------------------------------
def send(session: requests.Session, url: str, payload: dict) -> tuple[int | None, float]:
    """POST /predict; returns (status code or None on connection error, latency ms)."""
    start = time.perf_counter()
    try:
        status = session.post(f"{url}/predict", json=payload, timeout=TIMEOUT_S).status_code
    except requests.RequestException:
        status = None
    return status, (time.perf_counter() - start) * 1000


class Stats:
    """Running counters for the simulator."""

    def __init__(self) -> None:
        self.sent = 0
        self.by_class = {"2xx": 0, "4xx": 0, "5xx": 0, "errors": 0}
        self.by_kind: dict[str, int] = {}
        self.total_latency_ms = 0.0

    def record(self, kind: str, status: int | None, latency_ms: float) -> None:
        """Count one request."""
        self.sent += 1
        self.by_kind[kind] = self.by_kind.get(kind, 0) + 1
        self.total_latency_ms += latency_ms
        if status is None:
            self.by_class["errors"] += 1
        elif status >= 500:
            self.by_class["5xx"] += 1
        elif status >= 400:
            self.by_class["4xx"] += 1
        else:
            self.by_class["2xx"] += 1

    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.sent if self.sent else 0.0

    def line(self, elapsed_s: float) -> str:
        """One progress line."""
        c = self.by_class
        return (f"[{elapsed_s:5.0f}s] sent {self.sent:>5} | 2xx {c['2xx']:>5} | 4xx {c['4xx']:>4} | "
                f"5xx {c['5xx']:>3} | errors {c['errors']:>3} | avg {self.avg_latency_ms():6.1f} ms")


def run(url: str, mode: str, rps: float, duration: float, seed: int,
        data: Path = DEFAULT_DATA) -> Stats:
    """Send requests at roughly `rps` for `duration` seconds; never raises on HTTP errors."""
    rng = random.Random(seed)
    applicants = load_applicants(data)
    weights = purpose_weights(applicants)
    print(f"Simulating '{mode}' traffic to {url}: {rps} rps for {duration} s "
          f"({len(applicants):,} applicants, seed {seed})")

    stats = Stats()
    session = requests.Session()
    start = time.monotonic()
    next_report = start + REPORT_EVERY_S
    total = math.floor(rps * duration)
    for i in range(total):
        wait = start + i / rps - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        if time.monotonic() - start >= duration:
            break
        kind, payload = build_request(mode, applicants, rng, weights)
        status, latency_ms = send(session, url, payload)
        stats.record(kind, status, latency_ms)
        if time.monotonic() >= next_report:
            print(stats.line(time.monotonic() - start))
            next_report += REPORT_EVERY_S

    elapsed = time.monotonic() - start
    print_summary(stats, elapsed)
    return stats


def print_summary(stats: Stats, elapsed_s: float) -> None:
    """Final summary."""
    print("\n=== Summary ===")
    print(stats.line(elapsed_s))
    print(f"achieved {stats.sent / elapsed_s if elapsed_s else 0:.2f} rps over {elapsed_s:.1f} s | "
          f"by kind: {stats.by_kind}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Send simulated traffic to the loan offer API.")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--mode", choices=["normal", "drift", "bad", "mixed"], default="normal")
    parser.add_argument("--rps", type=float, default=5)
    parser.add_argument("--duration", type=float, default=120, help="seconds")
    parser.add_argument("--seed", type=int, default=RANDOM_STATE)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args(argv)
    if args.rps <= 0 or args.duration <= 0:
        parser.error("--rps and --duration must be positive")
    run(args.url.rstrip("/"), args.mode, args.rps, args.duration, args.seed, args.data)


if __name__ == "__main__":
    main()
