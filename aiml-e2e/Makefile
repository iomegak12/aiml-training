# Northwind Finance - loan offer prediction (educational demo)
# Run "make help" to list targets.

# Pick the venv Python for the current OS
ifeq ($(OS),Windows_NT)
PY := .venv/Scripts/python.exe
else
PY := .venv/bin/python
endif

.DEFAULT_GOAL := help

# Docker image (only our API image is built; Prometheus/Grafana use official images)
IMAGE   := iomega/northwind-loans-api
VERSION := 0.1.0
# Latest saved model version - "=" (lazy) so it is only computed by docker-build
MODEL_VERSION = $(shell $(PY) -c "from northwind_loans.registry import list_versions; print(list_versions()[-1])")

# "logs" is also a folder name, so every target must be .PHONY
.PHONY: help setup profile clean-data features train models predict-sample test serve \
        docker-build up down logs simulate-normal simulate-drift simulate-bad reset-logs monitor check-dashboards

help:
	@echo "Northwind Finance - make targets"
	@echo "  setup            create .venv (Python 3.12, uv) and install the package"
	@echo "  profile          profile the raw data"
	@echo "  clean-data       clean raw data into data/processed"
	@echo "  features         preview policy features on the processed data"
	@echo "  train            train, report and save the next model version"
	@echo "  models           list saved model versions"
	@echo "  predict-sample   predict on the sample applicants"
	@echo "  test             run the test suite"
	@echo "  serve            run the FastAPI app locally"
	@echo "  docker-build     build the API Docker image"
	@echo "  up / down        start / stop the Docker stack"
	@echo "  logs             follow the stack logs"
	@echo "  simulate-normal  normal traffic, 5 rps for 120 s"
	@echo "  simulate-drift   downturn traffic (income x0.6, score -80, 50% Personal), 300 s"
	@echo "  simulate-bad     30% invalid requests, 120 s"
	@echo "  reset-logs       truncate logs/predictions.jsonl to 0 bytes"
	@echo "  monitor          drift + fairness report from the audit log (last 30 min, exit 1 = investigate)"
	@echo "  check-dashboards print dashboard URLs and run every panel/alert query"

# ---- Available now ---------------------------------------------------------
setup:
	uv venv --python 3.12 --allow-existing .venv
	uv pip install --python $(PY) -e ".[dev]"

test:
	$(PY) -m pytest -q

profile:
	$(PY) -m northwind_loans.profiling

clean-data:
	$(PY) -m northwind_loans.cleaning

features:
	$(PY) -m northwind_loans.features

train:
	$(PY) -m northwind_loans.train

models:
	$(PY) -m northwind_loans.registry

predict-sample:
	$(PY) -m northwind_loans.predict

serve:
	$(PY) -m northwind_loans.api

docker-build:
	docker build --build-arg MODEL_VERSION=$(MODEL_VERSION) -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

SIM := $(PY) scripts/simulate_traffic.py

simulate-normal:
	$(SIM) --mode normal --duration 120

simulate-drift:
	$(SIM) --mode drift --duration 300

simulate-bad:
	$(SIM) --mode bad --duration 120

# Truncate the audit log to 0 bytes (never deletes it; the API keeps appending)
reset-logs:
	$(PY) -c "from northwind_loans.config import PREDICTION_LOG as p; p.parent.mkdir(exist_ok=True); open(p, 'w').close(); print(f'{p} truncated to {p.stat().st_size} bytes')"

# Drift + fairness report; exits 1 (make shows "Error 1") when a feature needs investigation
monitor:
	$(PY) -m northwind_loans.monitoring --since-minutes 30 --output reports/monitoring_report

check-dashboards:
	@echo "Grafana    : http://localhost:3000/d/loan-api/northwind-loan-offer-api"
	@echo "Prometheus : http://localhost:9090/alerts"
	$(PY) scripts/check_monitoring.py
