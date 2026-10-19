"""Request / response schemas (Pydantic v2) for the loan-offer API.

All validation lives here, so bad input returns HTTP 422 - never a 500.
Category values are the canonical ones produced by cleaning.CATEGORY_MAPS.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from northwind_loans.config import INCOME_PAISE_THRESHOLD, VALID_RANGES

FAIRNESS_NOTE = (
    "Used ONLY for fairness monitoring - never used by the model to compute the offer."
)

# OpenAPI example built from sample applicant NWF-035344
EXAMPLE_APPLICANT: dict = {
    "application_id": "NWF-035344",
    "annual_income": 1234000,
    "monthly_existing_emi": 0,
    "employment_type": "Business Owner",
    "loan_purpose": "Home",
    "requested_tenure_months": 144,
    "credit_score": 776,
    "years_employed": 6.5,
    "existing_loans_count": 0,
    "requested_amount": 4870000,
    "has_collateral": True,
    "gender": "Female",
    "age": 27,
}

_SCORE_MIN, _SCORE_MAX = VALID_RANGES["credit_score"]
_TENURE_MIN, _TENURE_MAX = VALID_RANGES["requested_tenure_months"]
_AGE_MIN, _AGE_MAX = VALID_RANGES["age"]


class ApplicantIn(BaseModel):
    """One loan application. Unknown fields are rejected (422)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [EXAMPLE_APPLICANT]})

    # required
    annual_income: float = Field(gt=0, le=INCOME_PAISE_THRESHOLD, description="Annual income (INR)")
    monthly_existing_emi: float = Field(ge=0, description="Current EMIs per month (INR)")
    employment_type: Literal["Salaried", "Self-Employed", "Business Owner"]
    loan_purpose: Literal["Home", "Personal", "Auto", "Education", "Business"]
    requested_tenure_months: int = Field(ge=_TENURE_MIN, le=_TENURE_MAX)

    # optional
    application_id: str | None = None
    credit_score: int | None = Field(
        None, ge=_SCORE_MIN, le=_SCORE_MAX,
        description="None for thin-file applicants (flagged for manual review)",
    )
    years_employed: float | None = Field(None, ge=0, le=50)
    existing_loans_count: int | None = Field(None, ge=0, le=20)
    requested_amount: float | None = Field(
        None, gt=0, description="Recorded only - not used by the model (anchoring risk)"
    )
    has_collateral: bool | None = None
    gender: Literal["Male", "Female", "Other"] | None = Field(None, description=FAIRNESS_NOTE)
    age: int | None = Field(None, ge=_AGE_MIN, le=_AGE_MAX, description=FAIRNESS_NOTE)


class OfferOut(BaseModel):
    """The loan offer for one applicant."""

    application_id: str | None
    offered_amount: int | None = Field(description="Final offer (INR); None = no offer")
    raw_model_estimate: int | None = Field(description="Model output before business rules")
    manual_review: bool
    review_reasons: list[str]
    rules_applied: list[str]
    model_version: int


class BatchIn(BaseModel):
    """1 to 1000 applications scored in one call."""

    model_config = ConfigDict(extra="forbid")

    applicants: list[ApplicantIn] = Field(min_length=1, max_length=1000)


class BatchOut(BaseModel):
    """Offers in the same order as the request."""

    results: list[OfferOut]
