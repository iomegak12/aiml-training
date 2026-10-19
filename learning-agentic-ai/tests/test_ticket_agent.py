"""Offline tests of the deep agent wiring, streaming output and plan approval,
using a scripted chat model instead of OpenAI."""

import pytest
from helpers import ScriptedModel, todos, tool_call
from langchain_core.messages import AIMessage

from ticket_agent import build_agent, build_planning_agent, new_thread, run_with_plan_approval, stream_agent


def test_agent_streams_tool_calls_results_and_answer(service, capsys):
    model = ScriptedModel(
        responses=[
            tool_call("get_location", {}, "call_1"),
            tool_call(
                "register_ticket",
                {
                    "raised_by": "Ram",
                    "title": "Network outage",
                    "description": "No internet on floor 2",
                    "priority": "Critical",
                    "department": "IT",
                },
                "call_2",
            ),
            AIMessage(
                content=[
                    {"type": "reasoning", "summary": [{"type": "summary_text", "text": "Ticket created."}]},
                    {"type": "text", "text": "Registered TKT-00001."},
                ]
            ),
        ]
    )
    agent = build_agent(model=model, ticket_service=service)

    interrupts = stream_agent(agent, "Log a network outage ticket", new_thread())

    out = capsys.readouterr().out
    assert interrupts == ()
    assert "🔧 get_location({})" in out
    assert "↳ get_location:" in out and "Bengaluru" in out
    assert "🔧 register_ticket(" in out
    assert "TKT-00001" in out
    assert "🧠 thinking: Ticket created." in out
    assert "🤖 Registered TKT-00001." in out
    assert service.get_ticket("TKT-00001").priority.value == "Critical"


def test_agent_remembers_thread(service):
    model = ScriptedModel(responses=[AIMessage(content="Hi Ram"), AIMessage(content="Your name is Ram")])
    agent = build_agent(model=model, ticket_service=service)
    config = new_thread()

    stream_agent(agent, "I am Ram", config)
    stream_agent(agent, "What is my name?", config)

    history = agent.get_state(config).values["messages"]
    assert [m.content for m in history] == ["I am Ram", "Hi Ram", "What is my name?", "Your name is Ram"]


def test_plan_rejected_then_approved_then_executed(service, capsys):
    model = ScriptedModel(
        responses=[
            tool_call("write_todos", todos(("Check weather", "pending")), "plan_1"),
            tool_call(
                "write_todos",
                todos(("Get my location", "in_progress"), ("Check weather there", "pending")),
                "plan_2",
            ),
            tool_call("get_location", {}, "call_1"),
            tool_call("get_weather", {"city": "Bengaluru"}, "call_2"),
            tool_call(
                "write_todos",
                todos(("Get my location", "completed"), ("Check weather there", "completed")),
                "plan_3",
            ),
            AIMessage(content="It is partly cloudy in Bengaluru."),
        ]
    )
    agent = build_planning_agent(model=model, ticket_service=service)
    answers = iter(["n", "Find my location first", "y"])
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    run_with_plan_approval(agent, "What's the weather where I am?", new_thread(), ask=ask)

    out = capsys.readouterr().out
    assert prompts == [
        "Approve this plan? (y/n): ",
        "What should change in the plan? ",
        "Approve this plan? (y/n): ",
    ]
    assert out.count("📋 Proposed plan") == 2
    assert "❌ Plan rejected" in out
    assert "✅ Plan approved" in out
    assert "Plan progress (auto-approved)" in out
    assert "🔧 get_weather(" in out
    assert "partly cloudy in Bengaluru" in out
    assert model.calls == 6


def test_plan_is_not_executed_before_approval(service):
    model = ScriptedModel(responses=[tool_call("write_todos", todos(("Register ticket", "pending")), "plan_1")])
    agent = build_planning_agent(model=model, ticket_service=service)
    config = new_thread()

    interrupts = stream_agent(agent, "Register a ticket", config)

    assert len(interrupts) == 1
    action = interrupts[0].value["action_requests"][0]
    assert action["name"] == "write_todos"
    assert service.find_tickets() == []
    assert model.calls == 1


@pytest.mark.parametrize("builder", [build_agent, build_planning_agent])
def test_agent_has_all_tools(service, builder):
    agent = builder(model=ScriptedModel(responses=[]), ticket_service=service)
    tool_names = set(agent.nodes["tools"].bound.tools_by_name)
    expected = {
        "register_ticket", "find_tickets", "get_ticket", "update_ticket", "resolve_ticket",
        "archive_ticket", "get_location", "get_weather", "get_current_time",
    }
    assert expected <= tool_names
    if builder is build_planning_agent:
        assert "write_todos" in tool_names
