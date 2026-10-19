from helpers import parse_sse, tool_call
from langchain_core.messages import AIMessage

ANSWER = AIMessage(
    content=[
        {"type": "reasoning", "summary": [{"type": "summary_text", "text": "Looking up location."}]},
        {"type": "text", "text": "It is partly cloudy in Bengaluru."},
    ]
)


def test_streaming_event_sequence(make_client, make_runtime):
    client = make_client(make_runtime(chat=[tool_call("get_location", {}, "c1"), ANSWER]))

    response = client.post("/chat-streaming", json={"message": "Weather where I am?"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "start"
    assert names[-1] == "done"
    assert names.index("tool_call") < names.index("tool_result") < names.index("token")

    data = dict(events)
    thread_id = data["start"]["thread_id"]
    assert data["tool_call"] == {"id": "c1", "name": "get_location", "args": {}, "subagent": False}
    assert data["tool_result"]["name"] == "get_location"
    assert "Bengaluru" in data["tool_result"]["content"]
    assert data["reasoning"]["text"] == "Looking up location."
    assert data["done"] == {"thread_id": thread_id, "reply": "It is partly cloudy in Bengaluru."}


def test_streaming_releases_thread_for_next_request(make_client, make_runtime):
    client = make_client(make_runtime(chat=[AIMessage(content="first"), AIMessage(content="second")]))

    thread_id = parse_sse(client.post("/chat-streaming", json={"message": "a"}).text)[0][1]["thread_id"]
    second = client.post("/chat-streaming", json={"message": "b", "thread_id": thread_id})

    assert dict(parse_sse(second.text))["done"]["reply"] == "second"


def test_streaming_error_event(make_client, make_runtime):
    client = make_client(make_runtime(chat=[RuntimeError("boom"), AIMessage(content="recovered")]))

    response = client.post("/chat-streaming", json={"message": "hi", "thread_id": "t-err"})

    events = parse_sse(response.text)
    assert [name for name, _ in events] == ["start", "error"]
    problem = events[1][1]
    assert problem["code"] == "INTERNAL_ERROR"
    assert problem["status"] == 500
    assert problem["request_id"] == response.headers["X-Request-ID"]

    # The thread was released despite the error.
    again = client.post("/chat-streaming", json={"message": "hi", "thread_id": "t-err"})
    assert dict(parse_sse(again.text))["done"]["reply"] == "recovered"


def test_streaming_rejects_plan_mode(make_client, make_runtime):
    response = make_client(make_runtime()).post("/chat-streaming", json={"message": "hi", "mode": "plan"})
    assert response.status_code == 422


def test_streaming_logged_with_reply(make_client, make_runtime, read_logs):
    client = make_client(make_runtime(chat=[AIMessage(content="streamed answer")]))

    response = client.post("/chat-streaming", json={"message": "hello"})

    entry = next(e for e in read_logs() if e.get("path") == "/chat-streaming")
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert entry["status"] == 200
    assert entry["streaming"] is True
    assert entry["user_message"] == "hello"
    assert entry["reply"] == "streamed answer"
