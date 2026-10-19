"""Northwind Finance - maximum loan offer prediction (educational demo)."""

from northwind_loans import config
from northwind_loans.config import (
    CREDIT_POLICY,
    INCOME_PAISE_THRESHOLD,
    LOG_DIR,
    LOG_LEVEL,
    MODEL_DIR,
    MODEL_NAME,
    PROCESSED_DATA,
    PROJECT_ROOT,
    RANDOM_STATE,
    RAW_DATA,
    REPORTS_DIR,
    SAMPLE_DATA,
    TARGET,
    VALID_RANGES,
)

__version__ = "0.1.0"

__all__ = [
    "config",
    "PROJECT_ROOT",
    "RAW_DATA",
    "SAMPLE_DATA",
    "PROCESSED_DATA",
    "REPORTS_DIR",
    "MODEL_DIR",
    "LOG_DIR",
    "LOG_LEVEL",
    "RANDOM_STATE",
    "TARGET",
    "MODEL_NAME",
    "CREDIT_POLICY",
    "VALID_RANGES",
    "INCOME_PAISE_THRESHOLD",
]
