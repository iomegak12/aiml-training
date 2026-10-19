"""Run every Grafana panel query and every Prometheus alert expression.

Panel queries are read from the dashboard JSON and alert rules from the running
Prometheus (/api/v1/rules), so this checks exactly what is deployed.

For alerts, the *signal* (expression without its trailing comparison, e.g.
`up{job="loan-api"}` instead of `up{job="loan-api"} == 0`) must return data; the
full expression returns data only when the alert condition is true.

Usage:
    python scripts/check_monitoring.py [--prometheus http://localhost:9090] [--dashboard PATH]

Exit code 1 if any panel query or alert signal is empty or fails.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import requests

DEFAULT_DASHBOARD = (
    Path(__file__).resolve().parents[1] / "monitoring" / "grafana" / "dashboards" / "loan_api.json"
)
TRAILING_COMPARISON = re.compile(r"\s*(==|!=|>=|<=|>|<)\s*-?[\d.]+(e[-+]?\d+)?\s*$", re.IGNORECASE)


def panel_queries(dashboard_path: Path) -> list[tuple[str, str]]:
    """(label, expr) for every target of every non-row panel."""
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    queries = []
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            queries.append((f"#{panel['id']} {panel['title']} [{target['refId']}]", target["expr"]))
    return queries


def alert_rules(prometheus: str) -> list[dict]:
    """Alerting rules currently loaded in Prometheus."""
    response = requests.get(f"{prometheus}/api/v1/rules", timeout=10)
    response.raise_for_status()
    groups = response.json()["data"]["groups"]
    return [rule for group in groups for rule in group["rules"] if rule["type"] == "alerting"]


def signal_of(expr: str) -> str:
    """Alert expression without its trailing threshold comparison."""
    return TRAILING_COMPARISON.sub("", " ".join(expr.split()))


def run_query(prometheus: str, expr: str) -> tuple[str, int, str]:
    """Instant query -> (status, number of series, first value)."""
    response = requests.get(f"{prometheus}/api/v1/query", params={"query": expr}, timeout=10)
    body = response.json()
    if body.get("status") != "success":
        return "ERROR", 0, body.get("error", "")[:40]
    result = body["data"]["result"]
    if not result:
        return "EMPTY", 0, "-"
    value = float(result[0]["value"][1])
    return "OK", len(result), f"{value:,.4g}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check dashboard and alert queries.")
    parser.add_argument("--prometheus", default="http://localhost:9090")
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD)
    args = parser.parse_args(argv)

    failures = 0
    print(f"{'PANEL QUERY':58}{'status':8}{'series':>7}  value")
    for label, expr in panel_queries(args.dashboard):
        status, series, value = run_query(args.prometheus, expr)
        failures += status != "OK"
        print(f"{label[:57]:58}{status:8}{series:>7}  {value}")

    rules = alert_rules(args.prometheus)
    print(f"\n{'ALERT (signal = expr without threshold)':42}{'signal':8}{'value':>12}"
          f"  {'full expr':10}{'state':10}health")
    for rule in rules:
        status, _, value = run_query(args.prometheus, signal_of(rule["query"]))
        full_status, _, _ = run_query(args.prometheus, rule["query"])
        failures += status != "OK"
        firing = "firing" if full_status == "OK" else "quiet"
        print(f"{rule['name']:42}{status:8}{value:>12}  {firing:10}{rule['state']:10}{rule['health']}")

    print(f"\n{len(rules)} alert rules loaded | problems: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
