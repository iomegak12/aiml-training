"""Static checks of the provisioned Grafana dashboard JSON."""

import json
from pathlib import Path

import pytest

from northwind_loans.config import PROJECT_ROOT

DASHBOARD_PATH = PROJECT_ROOT / "monitoring" / "grafana" / "dashboards" / "loan_api.json"


@pytest.fixture(scope="module")
def dashboard() -> dict:
    return json.loads(Path(DASHBOARD_PATH).read_text(encoding="utf-8"))


def panels(dashboard: dict) -> list[dict]:
    return [p for p in dashboard["panels"] if p["type"] != "row"]


def test_dashboard_settings(dashboard: dict) -> None:
    assert dashboard["uid"] == "loan-api"
    assert dashboard["title"] == "Northwind Loan Offer API"
    assert dashboard["refresh"] == "5s"
    assert dashboard["time"] == {"from": "now-15m", "to": "now"}
    assert dashboard["schemaVersion"] == 39


def test_three_rows_and_thirteen_panels(dashboard: dict) -> None:
    rows = [p["title"] for p in dashboard["panels"] if p["type"] == "row"]
    assert rows == ["Service health", "Model behaviour", "Data drift"]
    assert sorted(p["id"] for p in panels(dashboard)) == list(range(1, 14))


def test_every_query_uses_prometheus_datasource(dashboard: dict) -> None:
    for panel in panels(dashboard):
        assert panel["targets"], panel["title"]
        for target in panel["targets"]:
            assert target["datasource"]["uid"] == "prometheus"


def test_manual_review_label_matches_api(dashboard: dict) -> None:
    text = json.dumps(dashboard)
    assert 'manual_review=\\"true\\"' in text
    assert 'manual_review=\\"True\\"' not in text


def test_special_panels(dashboard: dict) -> None:
    by_id = {p["id"]: p for p in panels(dashboard)}
    assert by_id[5]["type"] == "barchart"
    assert by_id[12]["type"] == "bargauge" and by_id[12]["targets"][0]["format"] == "heatmap"
    assert by_id[13]["targets"][0]["legendFormat"] == "{{model_version}}"
    for panel_id in (7, 10, 11):  # reference drawn as a dashed second series
        override = by_id[panel_id]["fieldConfig"]["overrides"][0]
        assert override["matcher"]["options"] == "B"
        assert override["properties"][0]["value"]["fill"] == "dash"
