from io import StringIO
from pathlib import Path

from rich.console import Console

from api.banner import print_banner
from api.config import ApiSettings, app_version
from api.runtime import AgentRuntime, RuntimeInfo


def test_health(make_client, make_runtime):
    response = make_client(make_runtime()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "name": "IT Support Agent API", "version": app_version()}


def test_ready_when_all_checks_pass(make_client, make_runtime):
    response = make_client(make_runtime()).get("/ready")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ready"
    assert set(body["checks"]) == {"settings", "openai_api_key", "database", "agents"}
    assert all(check["ok"] for check in body["checks"].values())


def test_not_ready_without_api_key(make_client, make_runtime, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    response = make_client(make_runtime()).get("/ready")
    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "not_ready"
    assert body["checks"]["openai_api_key"] == {"ok": False, "detail": "OPENAI_API_KEY is not set"}


def test_not_ready_when_agents_missing(make_client, service):
    runtime = AgentRuntime(None, None, service, error="Missing credentials")
    body = make_client(runtime).get("/ready").json()
    assert body["checks"]["agents"]["ok"] is False
    assert "Missing credentials" in body["checks"]["agents"]["detail"]
    assert body["checks"]["database"]["ok"] is True


def test_openapi_and_docs(make_client, make_runtime):
    client = make_client(make_runtime())
    spec = client.get("/openapi.json").json()

    assert set(spec["paths"]) == {"/chat", "/chat-streaming", "/chat/decision", "/health", "/ready"}
    chat = spec["paths"]["/chat"]["post"]
    assert chat["summary"] == "Chat with the agent"
    assert "thread_id" in chat["description"]
    assert {"409", "422", "429", "502", "503"} <= set(chat["responses"])
    assert spec["info"]["license"]["name"] == "MIT"
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200


def test_banner_renders(tmp_path):
    output = StringIO()
    info = RuntimeInfo(model="openai:gpt-5.1", reasoning_effort="high", api_key_set=False, database_path="db.sqlite", error="no key")
    print_banner(ApiSettings(port=9000, log_dir=Path(tmp_path)), info, Console(file=output, width=140))

    text = output.getvalue()
    for expected in ["IT Support Agent API", "http://localhost:9000/docs", "openai:gpt-5.1", "MISSING", "DEGRADED", "100 req / 60s"]:
        assert expected in text
