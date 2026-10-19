import logging
from io import StringIO

from langchain_core.messages import AIMessage
from rich.console import Console

from api.logging_setup import ConsoleHandler


def test_request_logged_as_json(make_client, make_runtime, read_logs):
    client = make_client(make_runtime(chat=[AIMessage(content="Hello!")]))

    response = client.post("/chat?verbose=1", json={"message": "Hi there"}, headers={"User-Agent": "pytest-agent"})

    entry = next(e for e in read_logs() if e.get("path") == "/chat")
    assert entry["level"] == "INFO"
    assert entry["logger"] == "api.access"
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["method"] == "POST"
    assert entry["status"] == 200
    assert entry["query"] == "verbose=1"
    assert entry["client_ip"] == "testclient"
    assert entry["user_agent"] == "pytest-agent"
    assert entry["duration_ms"] >= 0
    assert entry["thread_id"] == response.json()["thread_id"]
    assert entry["message"] == "request"
    assert entry["user_message"] == "Hi there"
    assert entry["reply"] == "Hello!"
    assert entry["timestamp"].endswith("+00:00")


def test_incoming_request_id_is_reused(make_client, make_runtime, read_logs):
    client = make_client(make_runtime())

    response = client.get("/health", headers={"X-Request-ID": "trace-123"})

    assert response.headers["X-Request-ID"] == "trace-123"
    assert any(e.get("request_id") == "trace-123" for e in read_logs())


def test_invalid_request_id_is_replaced(make_client, make_runtime):
    response = make_client(make_runtime()).get("/health", headers={"X-Request-ID": "bad id with spaces"})
    assert response.headers["X-Request-ID"] != "bad id with spaces"


def test_errors_logged_with_traceback(make_client, make_runtime, read_logs):
    client = make_client(make_runtime(chat=[RuntimeError("boom")]))

    response = client.post("/chat", json={"message": "hi"})

    entries = read_logs()
    error = next(e for e in entries if e["level"] == "ERROR")
    assert "RuntimeError: boom" in error["exception"]
    access = next(e for e in entries if e.get("path") == "/chat")
    assert access["status"] == 500
    assert access["request_id"] == response.headers["X-Request-ID"]


def test_console_line_is_minimal():
    output = StringIO()
    handler = ConsoleHandler(Console(file=output, width=200))
    record = logging.LogRecord("api.access", logging.INFO, __file__, 1, "request", None, None)
    record.fields = {
        "method": "POST", "path": "/chat", "status": 200, "duration_ms": 1840.2,
        "client_ip": "127.0.0.1", "request_id": "abcdef1234567890", "user_message": "secret text",
    }

    handler.emit(record)

    line = output.getvalue().strip()
    for expected in ["POST", "/chat", "200", "1840ms", "127.0.0.1", "[abcdef12]"]:
        assert expected in line
    assert "secret text" not in line  # message bodies only go to the file
