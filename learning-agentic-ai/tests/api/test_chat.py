import httpx
import openai
import pytest
from helpers import tool_call
from langchain_core.messages import AIMessage

PROBLEM = "application/problem+json"


def _problem(response, status, code):
    assert response.status_code == status
    assert response.headers["content-type"] == PROBLEM
    body = response.json()
    assert body["status"] == status
    assert body["code"] == code
    assert body["request_id"] == response.headers["X-Request-ID"]
    return body


def test_chat_new_thread(make_client, make_runtime):
    client = make_client(make_runtime(chat=[AIMessage(content="Hello Ram!")]))

    response = client.post("/chat", json={"message": "Hi, I'm Ram"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Hello Ram!"
    assert body["status"] == "completed"
    assert body["mode"] == "chat"
    assert body["plan"] is None
    assert len(body["thread_id"]) == 36
    assert response.headers["X-Request-ID"]
    assert response.headers["X-RateLimit-Limit"] == "100"
    assert response.headers["X-RateLimit-Remaining"] == "99"


def test_chat_continues_thread(make_client, make_runtime):
    runtime = make_runtime(chat=[AIMessage(content="Hi Ram"), AIMessage(content="Your name is Ram")])
    client = make_client(runtime)

    thread_id = client.post("/chat", json={"message": "I am Ram"}).json()["thread_id"]
    second = client.post("/chat", json={"message": "What is my name?", "thread_id": thread_id})

    assert second.json()["thread_id"] == thread_id
    history = runtime.agent.get_state({"configurable": {"thread_id": thread_id}}).values["messages"]
    assert len(history) == 4


def test_chat_uses_ticket_tools(make_client, make_runtime, service):
    ticket = {
        "raised_by": "Priya",
        "title": "VPN down",
        "description": "Cannot connect",
        "priority": "High",
        "department": "Finance",
    }
    client = make_client(
        make_runtime(chat=[tool_call("register_ticket", ticket, "c1"), AIMessage(content="Created TKT-00001")])
    )

    response = client.post("/chat", json={"message": "Raise a ticket"})

    assert response.json()["reply"] == "Created TKT-00001"
    assert service.get_ticket("TKT-00001").title == "VPN down"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "   "},
        {"message": "hi", "thread_id": "has spaces"},
        {"message": "hi", "mode": "debug"},
        {"message": "hi", "unexpected": 1},
        {"message": "x" * 8001},
    ],
)
def test_chat_validation_errors(make_client, make_runtime, payload):
    response = make_client(make_runtime()).post("/chat", json=payload)
    body = _problem(response, 422, "VALIDATION_ERROR")
    assert body["errors"]
    assert body["instance"] == "/chat"


def test_agent_not_ready(make_client):
    from api.runtime import AgentRuntime

    client = make_client(AgentRuntime(None, None, None, error="OPENAI_API_KEY missing"))
    body = _problem(client.post("/chat", json={"message": "hi"}), 503, "AGENT_NOT_READY")
    assert "OPENAI_API_KEY missing" in body["detail"]


def test_upstream_auth_error(make_client, make_runtime):
    response = httpx.Response(401, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    error = openai.AuthenticationError("invalid key", response=response, body=None)
    client = make_client(make_runtime(chat=[error]))

    _problem(client.post("/chat", json={"message": "hi"}), 502, "UPSTREAM_AUTH_ERROR")


def test_unexpected_error_is_500_problem(make_client, make_runtime):
    client = make_client(make_runtime(chat=[RuntimeError("boom")]))

    body = _problem(client.post("/chat", json={"message": "hi"}), 500, "INTERNAL_ERROR")
    assert "boom" not in body["detail"]  # internals are not leaked


def test_thread_busy(make_client, make_runtime):
    runtime = make_runtime(chat=[AIMessage(content="ok")])
    client = make_client(runtime)
    _, state = runtime._thread("busy-thread", "chat")
    state.lock.acquire()
    try:
        _problem(client.post("/chat", json={"message": "hi", "thread_id": "busy-thread"}), 409, "THREAD_BUSY")
    finally:
        state.lock.release()


def test_unknown_route_is_problem(make_client, make_runtime):
    _problem(make_client(make_runtime()).get("/nope"), 404, "NOT_FOUND")


def test_method_not_allowed_is_problem(make_client, make_runtime):
    _problem(make_client(make_runtime()).get("/chat"), 405, "METHOD_NOT_ALLOWED")
