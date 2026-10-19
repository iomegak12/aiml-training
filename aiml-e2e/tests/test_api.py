"""Tests for the FastAPI service (TestClient runs the lifespan handler)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from northwind_loans.api.main import create_app
from northwind_loans.api.schemas import EXAMPLE_APPLICANT


@pytest.fixture(scope="module")
def client(trained_model_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    audit_log = tmp_path_factory.mktemp("logs") / "predictions.jsonl"
    with TestClient(create_app(trained_model_dir, audit_log)) as test_client:
        yield test_client


def applicant(**changes: object) -> dict:
    return {**EXAMPLE_APPLICANT, **changes}


def test_health_and_ready(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/ready")
    assert response.status_code == 200 and response.json()["status"] == "ready"


def test_app_version_comes_from_metadata(client: TestClient) -> None:
    info = client.get("/openapi.json").json()["info"]
    assert info["version"] == "1"
    assert "NEVER use this API for real credit decisions" in info["description"]


def test_predict_example(client: TestClient) -> None:
    response = client.post("/predict", json=EXAMPLE_APPLICANT)
    assert response.status_code == 200
    body = response.json()
    assert body["application_id"] == "NWF-035344"
    assert isinstance(body["offered_amount"], int) and body["offered_amount"] % 1000 == 0
    assert body["model_version"] == 1


def test_thin_file_applicant_is_flagged(client: TestClient) -> None:
    body = client.post("/predict", json=applicant(credit_score=None)).json()
    assert body["manual_review"] is True
    assert body["review_reasons"] == ["credit_score_missing"]


def test_credit_score_950_returns_422(client: TestClient) -> None:
    response = client.post("/predict", json=applicant(credit_score=950))
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "credit_score"]
    assert "less than or equal to 900" in error["msg"]


def test_unknown_loan_purpose_returns_422(client: TestClient) -> None:
    response = client.post("/predict", json=applicant(loan_purpose="Holiday"))
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "literal_error"


@pytest.mark.parametrize(
    "bad",
    [
        {"annual_income": 0},
        {"annual_income": 62_400_000},  # paise-scaled income
        {"requested_tenure_months": 400},
        {"credit_scor": 700},           # typo -> extra field forbidden
    ],
)
def test_other_bad_inputs_return_422(client: TestClient, bad: dict) -> None:
    assert client.post("/predict", json=applicant(**bad)).status_code == 422


def test_missing_required_field_returns_422(client: TestClient) -> None:
    body = {k: v for k, v in EXAMPLE_APPLICANT.items() if k != "annual_income"}
    response = client.post("/predict", json=body)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "missing"


def test_batch(client: TestClient) -> None:
    payload = {"applicants": [applicant(application_id="A-1"), applicant(application_id="B-2")]}
    response = client.post("/predict/batch", json=payload)
    assert response.status_code == 200
    assert [r["application_id"] for r in response.json()["results"]] == ["A-1", "B-2"]


def test_batch_of_3(client: TestClient) -> None:
    ids = ["B-1", "B-2", "B-3"]
    payload = {"applicants": [applicant(application_id=i, loan_purpose=p)
                              for i, p in zip(ids, ["Home", "Auto", "Personal"])]}
    response = client.post("/predict/batch", json=payload)
    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["application_id"] for r in results] == ids
    assert all(r["offered_amount"] % 1000 == 0 for r in results)


def test_metrics_contains_key_values(client: TestClient) -> None:
    client.post("/predict", json=EXAMPLE_APPLICANT)
    text = client.get("/metrics").text
    assert 'loan_api_requests_total{endpoint="/predict",method="POST",status_code="200"}' in text
    assert "loan_model_predictions_total{" in text
    assert "loan_model_offer_amount_inr_count" in text
    assert 'loan_model_info{model_version="1"' in text


def test_batch_with_one_bad_item_returns_422(client: TestClient) -> None:
    payload = {"applicants": [applicant(), applicant(requested_tenure_months=-12)]}
    response = client.post("/predict/batch", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][:3] == ["body", "applicants", 1]


def test_empty_batch_returns_422(client: TestClient) -> None:
    assert client.post("/predict/batch", json={"applicants": []}).status_code == 422


def test_model_info_is_compact(client: TestClient) -> None:
    info = client.get("/model-info").json()
    assert info["version"] == 1 and "metrics" in info and "excluded_features" in info
    assert "reference_profile" not in info and "signature" not in info


def test_openapi_has_example_and_fairness_note(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()["components"]["schemas"]["ApplicantIn"]
    assert schema["examples"][0]["application_id"] == "NWF-035344"
    assert "fairness monitoring" in schema["properties"]["gender"]["description"]


def test_no_model_means_not_ready(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path, tmp_path / "predictions.jsonl")) as no_model:
        assert no_model.get("/health").status_code == 200
        assert no_model.get("/ready").status_code == 503
        assert no_model.post("/predict", json=EXAMPLE_APPLICANT).status_code == 503
