from helpers import todos, tool_call
from langchain_core.messages import AIMessage

TICKET = {
    "raised_by": "Ramkumar",
    "title": "Prepare for rain",
    "description": "Facilities to prepare for rain",
    "priority": "Medium",
    "department": "Admin",
}


def _plan_script():
    return [
        tool_call("write_todos", todos(("Register ticket", "pending")), "p1"),
        tool_call("write_todos", todos(("Check weather", "in_progress"), ("Register ticket", "pending")), "p2"),
        tool_call("get_weather", {"city": "Bengaluru"}, "c1"),
        tool_call("register_ticket", TICKET, "c2"),
        tool_call("write_todos", todos(("Check weather", "completed"), ("Register ticket", "completed")), "p3"),
        AIMessage(content="Registered TKT-00001 for the facilities team."),
    ]


def test_plan_reject_revise_approve_execute(make_client, make_runtime, service):
    client = make_client(make_runtime(plan=_plan_script()))

    proposed = client.post("/chat", json={"message": "Prepare facilities for the weather", "mode": "plan"}).json()
    assert proposed["status"] == "awaiting_approval"
    assert proposed["mode"] == "plan"
    assert proposed["plan"] == [{"content": "Register ticket", "status": "pending"}]
    assert proposed["reply"] is None
    thread_id = proposed["thread_id"]

    revised = client.post(
        "/chat/decision", json={"thread_id": thread_id, "approve": False, "feedback": "Check the weather first"}
    ).json()
    assert revised["status"] == "awaiting_approval"
    assert [step["content"] for step in revised["plan"]] == ["Check weather", "Register ticket"]
    assert service.find_tickets() == []  # nothing executed before approval

    done = client.post("/chat/decision", json={"thread_id": thread_id, "approve": True}).json()
    assert done["status"] == "completed"
    assert done["reply"] == "Registered TKT-00001 for the facilities team."
    assert service.get_ticket("TKT-00001").department == "Admin"


def test_decision_unknown_thread(make_client, make_runtime):
    response = make_client(make_runtime()).post("/chat/decision", json={"thread_id": "missing", "approve": True})
    assert response.status_code == 404
    assert response.json()["code"] == "THREAD_NOT_FOUND"


def test_decision_without_pending_plan(make_client, make_runtime):
    client = make_client(make_runtime(plan=[AIMessage(content="Nothing to plan, it's 10:00.")]))

    first = client.post("/chat", json={"message": "Time?", "mode": "plan"}).json()
    assert first["status"] == "completed"

    response = client.post("/chat/decision", json={"thread_id": first["thread_id"], "approve": True})
    assert response.status_code == 409
    assert response.json()["code"] == "NO_PENDING_PLAN"


def test_new_plan_request_while_plan_pending(make_client, make_runtime):
    client = make_client(make_runtime(plan=_plan_script()))
    thread_id = client.post("/chat", json={"message": "Do it", "mode": "plan"}).json()["thread_id"]

    response = client.post("/chat", json={"message": "Something else", "mode": "plan", "thread_id": thread_id})

    assert response.status_code == 409
    assert response.json()["code"] == "PLAN_PENDING"


def test_thread_mode_mismatch(make_client, make_runtime):
    client = make_client(make_runtime(chat=[AIMessage(content="hi")], plan=_plan_script()))
    chat_thread = client.post("/chat", json={"message": "hi"}).json()["thread_id"]

    as_plan = client.post("/chat", json={"message": "plan it", "mode": "plan", "thread_id": chat_thread})
    decision = client.post("/chat/decision", json={"thread_id": chat_thread, "approve": True})

    assert as_plan.status_code == decision.status_code == 409
    assert as_plan.json()["code"] == decision.json()["code"] == "THREAD_MODE_MISMATCH"
