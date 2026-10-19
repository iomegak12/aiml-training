"""Tests for request ids, Prometheus metrics, JSON logs and the prediction audit log."""

import json
import logging
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from northwind_loans.api import observability as obs
from northwind_loans.api.main import create_app
from northwind_loans.api.schemas import EXAMPLE_APPLICANT

METRIC_NAMES = [
    "loan_api_requests_total", "loan_api_request_duration_seconds",
    "loan_api_requests_in_progress", "loan_api_validation_errors_total",
    "loan_model_predictions_total", "loan_model_offer_amount_inr",
    "loan_model_offer_to_income_ratio", "loan_model_input_annual_income_inr",
    "loan_model_input_credit_score", "loan_model_reference_mean", "loan_model_info",
]


def sample(name: str, **labels: str) -> float:
    """Current value of a metric sample (0 if not yet created)."""
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.fixture(scope="module")
def audit_log(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("logs") / "predictions.jsonl"


@pytest.fixture(scope="module")
def client(trained_model_dir: Path, audit_log: Path) -> Iterator[TestClient]:
    with TestClient(create_app(trained_model_dir, audit_log)) as test_client:
        yield test_client


def test_request_id_is_echoed_or_generated(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "demo-123"})
    assert response.headers["X-Request-ID"] == "demo-123"
    generated = client.get("/health").headers["X-Request-ID"]
    assert uuid.UUID(generated).version == 4


def test_metrics_endpoint(client: TestClient) -> None:
    client.post("/predict", json=EXAMPLE_APPLICANT)  # make sure every metric has data
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    for name in METRIC_NAMES:
        assert name in response.text, name


def test_known_label_series_start_at_zero(client: TestClient) -> None:
    text = client.get("/metrics").text
    assert 'loan_model_predictions_total{loan_purpose="Education",manual_review="true"}' in text
    assert 'loan_api_validation_errors_total{field="requested_tenure_months"}' in text
    assert 'loan_api_requests_total{endpoint="/predict/batch",method="POST",status_code="503"}' in text


def test_metrics_requests_are_not_counted(client: TestClient) -> None:
    before = sample("loan_api_requests_total", method="GET", endpoint="/metrics", status_code="200")
    client.get("/metrics")
    after = sample("loan_api_requests_total", method="GET", endpoint="/metrics", status_code="200")
    assert before == after == 0


def test_request_counter_and_histogram(client: TestClient) -> None:
    labels = {"method": "GET", "endpoint": "/health", "status_code": "200"}
    before = sample("loan_api_requests_total", **labels)
    timed = sample("loan_api_request_duration_seconds_count", endpoint="/health")
    client.get("/health")
    assert sample("loan_api_requests_total", **labels) == before + 1
    assert sample("loan_api_request_duration_seconds_count", endpoint="/health") == timed + 1
    assert sample("loan_api_requests_in_progress") == 0


def test_validation_errors_counted_and_body_unchanged(client: TestClient) -> None:
    score_before = sample("loan_api_validation_errors_total", field="credit_score")
    purpose_before = sample("loan_api_validation_errors_total", field="loan_purpose")
    response = client.post("/predict", json={**EXAMPLE_APPLICANT, "credit_score": 950,
                                              "loan_purpose": "Holiday"})
    assert response.status_code == 422
    assert {e["loc"][-1] for e in response.json()["detail"]} == {"credit_score", "loan_purpose"}
    assert sample("loan_api_validation_errors_total", field="credit_score") == score_before + 1
    assert sample("loan_api_validation_errors_total", field="loan_purpose") == purpose_before + 1
    labels = {"method": "POST", "endpoint": "/predict", "status_code": "422"}
    assert sample("loan_api_requests_total", **labels) >= 1


def test_model_metrics_increase(client: TestClient) -> None:
    labels = {"loan_purpose": "Home", "manual_review": "false"}
    before = sample("loan_model_predictions_total", **labels)
    offers = sample("loan_model_offer_amount_inr_count")
    scores = sample("loan_model_input_credit_score_count")
    client.post("/predict", json=EXAMPLE_APPLICANT)
    client.post("/predict", json={**EXAMPLE_APPLICANT, "credit_score": None})  # no score observed
    assert sample("loan_model_predictions_total", **labels) == before + 1
    assert sample("loan_model_offer_amount_inr_count") == offers + 2
    assert sample("loan_model_input_credit_score_count") == scores + 1


def test_reference_and_info_gauges(client: TestClient) -> None:
    assert sample("loan_model_reference_mean", feature="annual_income") > 0
    assert sample("loan_model_reference_mean", feature="predicted_offer") > 0
    metadata = client.app.state.predictor.metadata
    assert sample("loan_model_info", model_version="1", trained_at=metadata["created_at"],
                  sklearn_version=metadata["sklearn_version"]) == 1


def test_audit_log_one_line_per_applicant_without_pii(client: TestClient, audit_log: Path) -> None:
    lines_before = audit_log.read_text(encoding="utf-8").splitlines() if audit_log.exists() else []
    payload = {"applicants": [EXAMPLE_APPLICANT, {**EXAMPLE_APPLICANT, "application_id": "X-2"}]}
    response = client.post("/predict/batch", json=payload, headers={"X-Request-ID": "batch-1"})
    assert response.status_code == 200
    new_lines = audit_log.read_text(encoding="utf-8").splitlines()[len(lines_before):]
    assert len(new_lines) == 2
    for line in new_lines:
        entry = json.loads(line)
        assert entry["request_id"] == "batch-1" and entry["endpoint"] == "/predict/batch"
        assert "age" not in entry["input"] and "gender" not in entry["input"]
        assert entry["input"]["annual_income"] == EXAMPLE_APPLICANT["annual_income"]
        assert isinstance(entry["output"]["offered_amount"], int)
    assert json.loads(new_lines[1])["input"]["application_id"] == "X-2"


def test_uvicorn_color_message_is_dropped() -> None:
    record = logging.LogRecord("uvicorn.error", logging.INFO, "", 0, "Started", None, None)
    record.color_message = "\x1b[36mStarted\x1b[0m"
    assert obs.DropColorMessage().filter(record)
    line = json.loads(obs.json_formatter().format(record))
    assert "color_message" not in line and line["message"] == "Started"


def test_request_log_line_is_json_with_fields(client: TestClient,
                                              caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger=obs.request_logger.name):
        client.get("/ready", headers={"X-Request-ID": "log-1"})
    record = [r for r in caplog.records if r.name == obs.request_logger.name][-1]
    line = json.loads(obs.json_formatter().format(record))
    assert line["message"] == "request" and line["level"] == "INFO"
    assert line["request_id"] == "log-1" and line["endpoint"] == "/ready"
    assert line["status_code"] == 200 and line["model_version"] == 1
    assert line["duration_ms"] >= 0 and "timestamp" in line
