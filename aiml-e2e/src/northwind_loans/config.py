"""Central configuration for the Northwind Finance loan-offer project.

Environment-specific settings (paths, log level, random state) can be
overridden in a `.env` file at the project root. Business rules (target
column, credit policy, valid ranges) live here in code on purpose.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Project root and .env
# --------------------------------------------------------------------------
# config.py -> northwind_loans -> src -> <project root>
_DEFAULT_ROOT: Path = Path(__file__).resolve().parents[2]

load_dotenv(_DEFAULT_ROOT / ".env")

PROJECT_ROOT: Path = Path(os.getenv("PROJECT_ROOT") or _DEFAULT_ROOT).resolve()


def _path_from_env(name: str, default: Path) -> Path:
    """Return the path in env var `name`, or `default` if it is not set.

    Relative paths are resolved against PROJECT_ROOT.
    """
    value = os.getenv(name)
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
RAW_DATA: Path = _path_from_env(
    "RAW_DATA", PROJECT_ROOT / "data" / "raw" / "loan_applications_raw.csv"
)
SAMPLE_DATA: Path = _path_from_env(
    "SAMPLE_DATA", PROJECT_ROOT / "data" / "sample" / "sample_applicants.csv"
)
PROCESSED_DATA: Path = _path_from_env("PROCESSED_DATA", PROJECT_ROOT / "data" / "processed")
REPORTS_DIR: Path = _path_from_env("REPORTS_DIR", PROJECT_ROOT / "reports")
MODEL_DIR: Path = _path_from_env("MODEL_DIR", PROJECT_ROOT / "models")
LOG_DIR: Path = _path_from_env("LOG_DIR", PROJECT_ROOT / "logs")
PREDICTION_LOG: Path = LOG_DIR / "predictions.jsonl"  # API audit log, one JSON line per applicant

# --------------------------------------------------------------------------
# Runtime settings
# --------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
RANDOM_STATE: int = int(os.getenv("RANDOM_STATE", "51"))

# API server (python -m northwind_loans.api)
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

# --------------------------------------------------------------------------
# Modelling
# --------------------------------------------------------------------------
TARGET: str = "max_loan_offered"
MODEL_NAME: str = "loan_offer_model"

# Secret used to sign model metadata (HMAC-SHA256). Set your own in .env.
DEFAULT_SIGNING_KEY: str = "dev-only-insecure-key"
MODEL_SIGNING_KEY: str = os.getenv("MODEL_SIGNING_KEY") or DEFAULT_SIGNING_KEY

# --------------------------------------------------------------------------
# Northwind credit policy (provided by the credit team)
# FOIR = Fixed Obligations to Income Ratio: share of monthly income
# allowed for all EMIs combined.
# --------------------------------------------------------------------------
CREDIT_POLICY: dict = {
    "rate_card_pct": {
        "Home": 8.6,
        "Personal": 12.5,
        "Auto": 9.2,
        "Education": 10.0,
        "Business": 13.5,
    },
    "income_multiple_cap": {
        "Home": 5.0,
        "Personal": 1.5,
        "Auto": 1.2,
        "Education": 1.5,
        "Business": 2.0,
    },
    "foir_by_credit_band": {
        "<600": 0.40,
        "600-649": 0.40,
        "650-699": 0.45,
        "700-749": 0.50,
        "750+": 0.55,
    },
    "salaried_foir_bonus": 0.05,
    # Bands from 650 upwards get no haircut (1.0); listed explicitly for clarity.
    "credit_haircut": {
        "<600": 0.5,
        "600-649": 0.8,
        "650-699": 1.0,
        "700-749": 1.0,
        "750+": 1.0,
    },
    "absolute_cap_income_multiple": 5,
    "round_offer_to": 1000,
    "manual_review_rules": {
        "credit_score_below": 600,
        "dti_above": 0.6,
        "credit_score_missing": True,
    },
}

# --------------------------------------------------------------------------
# Data validation
# --------------------------------------------------------------------------
VALID_RANGES: dict[str, tuple[int, int]] = {
    "age": (18, 75),
    "credit_score": (300, 900),
    "requested_tenure_months": (6, 360),
    "dependents": (0, 10),
}

# Annual incomes above 2 crore are treated as suspicious (likely entered in paise).
INCOME_PAISE_THRESHOLD: int = 20_000_000
